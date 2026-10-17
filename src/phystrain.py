#!/usr/bin/env python3
"""
phystrain.py - Phase 3: fine-tune LiquidAI/LFM2.5-1.2B-Thinking or Qwen/Qwen3.5-2B (non-thinking mode,
--no-thinking) with DoRA (or LoRA) on a free T4.

Commands
  check   load the data and tokenizer, copy the model's real <think> format from your evaluation
          outputs, show exactly which tokens are trained, list the layers that get adapters
  train   the training loop (resumable; safe to interrupt; rerun the same command to continue)
  sample  generate answers with a checkpoint for a few validation questions
  merge   merge an adapter into the base model and save a full model (for publishing)

Design (each choice is explained where it is implemented)
  * Loss: cross-entropy on the assistant part only (thinking + answer + end token), averaged over
    every trained token in the optimizer step. Logits are computed only at trained positions, in
    chunks recomputed in the backward pass (Qwen3.5 has a 248K-token vocabulary).
  * Base model frozen in fp16; adapter weights in fp32; fp16 autocast with a gradient scaler (T4
    has no bf16). Gradient checkpointing on.
  * Batches are packed by token budget (default 4,096 tokens per micro-batch) and accumulated to
    about 16 examples per optimizer step. Similar lengths are grouped to waste little padding.
  * AdamW, linear warm-up then cosine decay to 10% of the peak learning rate, gradient clipping.
  * Checkpoints to Drive every N steps (adapter + optimizer + scheduler + scaler), so a Colab
    disconnect loses at most N steps.
"""
import argparse
import collections
import csv
import hashlib
import json
import math
import os
import random
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

VERSION = "1.4"
MODEL_ID = "LiquidAI/LFM2.5-1.2B-Thinking"
LFM_TARGETS = ["q_proj", "k_proj", "v_proj", "out_proj", "in_proj", "w1", "w2", "w3"]
# Qwen3.5: full attention (q/k/v/o_proj), Gated DeltaNet linear attention (in_proj_qkv, in_proj_z, out_proj; the tiny
# in_proj_a / in_proj_b with 16 outputs are left out) and the MLP. Only the text model is loaded (no vision tower).
QWEN35_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "in_proj_qkv", "in_proj_z", "out_proj",
                  "gate_proj", "up_proj", "down_proj"]
KEY_DEFAULTS = {"no_thinking": False, "max_train": 0}  # settings added later; older runs had these values


def is_lfm(model_id):
    return "lfm" in (model_id or "").lower()


def resolve_targets(a):
    if getattr(a, "targets", "auto") != "auto":
        return a.targets
    return ",".join(LFM_TARGETS if is_lfm(a.model) else QWEN35_TARGETS)


def render_prompt(tok, messages, a):
    """Chat prompt as the model will see it at evaluation. Non-LFM models drop the 'trained by Liquid AI' system
    message (a wrong identity for them); --no-thinking renders with enable_thinking=False (Qwen3.5: an empty
    '<think>\n\n</think>\n\n' block is part of the prompt)."""
    msgs = messages if is_lfm(a.model) else [m for m in messages
                                             if not (m["role"] == "system" and "Liquid AI" in m["content"])]
    kw = {"enable_thinking": False} if getattr(a, "no_thinking", False) else {}
    return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, **kw)
DEFAULT_OPEN, DEFAULT_CLOSE = "<think>\n", "\n</think>\n\n"


def log(*a):
    print(*a, flush=True)


def import_peft():
    """Imports PEFT. Colab ships torchao 0.10, and new PEFT raises ImportError for any torchao older than 0.16 as
    soon as it builds an adapter layer, although nothing here uses torchao. In that case PEFT is told that
    torchao is not installed (same effect as `pip uninstall torchao`)."""
    import peft
    try:
        from importlib import metadata
        v = tuple(int(x) for x in re.findall(r"\d+", metadata.version("torchao"))[:2])
    except Exception:
        return peft
    if v < (0, 16):
        for name, mod in list(sys.modules.items()):
            if (name == "peft" or name.startswith("peft.")) and callable(getattr(mod, "is_torchao_available", None)):
                mod.is_torchao_available = lambda: False
        log("note: ignoring Colab's old torchao %s (PEFT rejects it and it is not needed)" % ".".join(map(str, v)))
    return peft


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def read_jsonl(path):
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, path)


# --------------------------------------------------------------------------------------
# Pure logic (no torch): tested without a GPU
# --------------------------------------------------------------------------------------

def detect_think_format(completions):
    """Copy the base model's own spacing around <think> ... </think> from its evaluation answers."""
    opens, closes = collections.Counter(), collections.Counter()
    for c in completions:
        if "</think>" not in c:
            continue
        m = re.match(r"^(\s*<think>[ \t]*\n*)", c)
        if m:
            opens[m.group(1).lstrip()] += 1
        m = re.search(r"(\n*[ \t]*</think>[ \t]*\n*)", c)
        if m:
            closes[m.group(1)] += 1
    if not opens or not closes:
        return DEFAULT_OPEN, DEFAULT_CLOSE, 0
    return opens.most_common(1)[0][0], closes.most_common(1)[0][0], sum(closes.values())


def build_target(think, answer, open_str, close_str, end_text, plain=False):
    if plain:  # non-thinking mode: the reasoning is ordinary visible text before the answer
        return think.strip() + "\n\n" + answer.strip() + end_text
    return open_str + think.strip() + close_str + answer.strip() + end_text


def plan_steps(lengths, examples_per_step, tokens_per_micro, epochs, seed, chunk=512, max_micro=8):
    """Deterministic list of optimizer steps; each step is a list of micro-batches of example indices.

    Within shuffled chunks of 512 examples, examples are sorted by length and packed so that
    (batch size x longest example) <= tokens_per_micro. Micro-batches are then grouped into steps of
    about `examples_per_step` examples, and the step order is shuffled again."""
    steps = []
    for ep in range(epochs):
        rnd = random.Random(seed * 1000 + ep)
        idx = list(range(len(lengths)))
        rnd.shuffle(idx)
        micros = []
        for s in range(0, len(idx), chunk):
            part = sorted(idx[s:s + chunk], key=lambda i: lengths[i])
            cur = []
            for i in part:
                longest = max([lengths[j] for j in cur] + [lengths[i]])
                if cur and (longest * (len(cur) + 1) > tokens_per_micro or len(cur) >= max_micro):
                    micros.append(cur)
                    cur = []
                cur.append(i)
            if cur:
                micros.append(cur)
        rnd.shuffle(micros)
        cur, n = [], 0
        for mb in micros:
            cur.append(mb)
            n += len(mb)
            if n >= examples_per_step:
                steps.append({"epoch": ep, "micro": cur})
                cur, n = [], 0
        if cur:
            steps.append({"epoch": ep, "micro": cur})
    return steps


def lr_factor(step, total, warmup, floor=0.1):
    if step < warmup:
        return (step + 1) / max(1, warmup)
    p = (step - warmup) / max(1, total - warmup)
    return floor + (1 - floor) * 0.5 * (1 + math.cos(math.pi * min(1.0, p)))


def data_fingerprint(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:12]


def format_health(texts, finished, open_str="<think>", plain=False):
    """Share of answers that close the thinking section, contain a boxed answer, and stop on their own."""
    n = max(len(texts), 1)
    if plain:  # no thinking section to close
        boxed = sum(1 for t in texts if "\\boxed" in t)
        return {"closed_thinking": 1.0, "boxed_after_thinking": boxed / n, "stopped": sum(finished) / n}
    closed = sum(1 for t in texts if "</think>" in t)
    boxed = sum(1 for t in texts if "\\boxed" in t.split("</think>")[-1] and "</think>" in t)
    return {"closed_thinking": closed / n, "boxed_after_thinking": boxed / n, "stopped": sum(finished) / n}


# --------------------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------------------

class Encoded:
    __slots__ = ("ids", "n_prompt", "id", "style")

    def __init__(self, ids, n_prompt, ex_id, style):
        self.ids, self.n_prompt, self.id, self.style = ids, n_prompt, ex_id, style


def think_format(workdir, base_run="lfm25-1.2b-thinking"):
    rows = []
    for b in ("ugphysics", "physicseval", "math500"):
        p = os.path.join(workdir, "runs", base_run, "gen_%s.jsonl" % b)
        if os.path.exists(p):
            rows += [r.get("completion", "") for r in read_jsonl(p)[:400]]
    o, c, n = detect_think_format(rows)
    note = ("copied from %d of the base model's own answers" % n) if n else "base answers not found; using the default"
    return o, c, note


def encode_all(tok, rows, open_str, close_str, end_text, max_len, a=None):
    if a is None:
        prompts = [tok.apply_chat_template(r["messages"], tokenize=False, add_generation_prompt=True) for r in rows]
    else:
        prompts = [render_prompt(tok, r["messages"], a) for r in rows]
    plain = bool(a is not None and getattr(a, "no_thinking", False))
    targets = [build_target(r["think"], r["answer"], open_str, close_str, end_text, plain) for r in rows]
    out, dropped = [], 0
    for s in range(0, len(rows), 1000):
        p_ids = tok(prompts[s:s + 1000], add_special_tokens=False)["input_ids"]
        t_ids = tok(targets[s:s + 1000], add_special_tokens=False)["input_ids"]
        for k, (p, t) in enumerate(zip(p_ids, t_ids)):
            if len(p) + len(t) > max_len:
                dropped += 1
                continue
            r = rows[s + k]
            out.append(Encoded(p + t, len(p), r.get("id"), r.get("style")))
    return out, dropped, prompts, targets


# --------------------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------------------

def load_base(model_id, dtype_name="float16"):
    """Text-only causal LM. For Qwen3.5 (a vision-language checkpoint) AutoModelForCausalLM loads the language
    model alone, which is what the evaluation harness loads too, so adapters match."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    dtype = getattr(torch, dtype_name)
    tok = AutoTokenizer.from_pretrained(model_id)
    try:
        model = AutoModelForCausalLM.from_pretrained(model_id, dtype=dtype)
    except TypeError:
        model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=dtype)
    if next(model.parameters()).dtype != dtype:
        model = model.to(dtype)
    return tok, model


def adapter_targets(model, wanted):
    import torch.nn as nn
    found = collections.Counter()
    for name, mod in model.named_modules():
        last = name.split(".")[-1]
        if last in wanted and isinstance(mod, nn.Linear) and "lm_head" not in name:
            found[last] += 1
    return found


def end_token_text(tok):
    eos = tok.convert_tokens_to_ids("<|im_end|>")
    if isinstance(eos, int) and eos >= 0 and eos != tok.unk_token_id:
        return "<|im_end|>", eos
    return tok.eos_token, tok.eos_token_id


# --------------------------------------------------------------------------------------
# check
# --------------------------------------------------------------------------------------

def cmd_check(a):
    data_dir = os.path.join(a.workdir, "train_data", a.data)
    train = read_jsonl(os.path.join(data_dir, "train.jsonl"))
    val = read_jsonl(os.path.join(data_dir, "val.jsonl"))
    log("data %s: %d training, %d validation examples" % (a.data, len(train), len(val)))
    styles = collections.Counter(r["style"] for r in train)
    log("  styles:", dict(styles))
    no_think = sum(1 for r in train if not r.get("think", "").strip())
    no_end = sum(1 for r in train if r["style"] in ("ug", "knowledge", "math") and "\\boxed{" not in r["answer"])
    log("  examples without a thinking trace: %d (must be 0)" % no_think)
    log("  boxed-style examples without a boxed answer: %d (must be 0)" % no_end)

    if a.no_thinking:
        open_str, close_str, note = "", "", "no thinking section: reasoning is trained as plain text"
    else:
        open_str, close_str, note = think_format(a.workdir)
    log("\nthink format (%s): open=%r close=%r" % (note, open_str, close_str))

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(a.model)
    end_text, end_id = end_token_text(tok)
    log("end token %r -> id %s" % (end_text, end_id))
    for t in ("<think>", "</think>"):
        ids = tok(t, add_special_tokens=False)["input_ids"]
        log("  %r tokenizes to %s" % (t, ids))
    enc, dropped, prompts, targets = encode_all(tok, train[:3000], open_str, close_str, end_text, a.max_len, a)
    lens = sorted(len(e.ids) for e in enc)
    tr = sorted(len(e.ids) - e.n_prompt for e in enc)
    q = lambda xs, p: xs[min(len(xs) - 1, int(p * len(xs)))] if xs else 0
    log("\nfirst %d examples: total tokens median %d, p90 %d, max %d | trained tokens median %d, p90 %d | %d too long"
        % (len(enc), q(lens, .5), q(lens, .9), lens[-1] if lens else 0, q(tr, .5), q(tr, .9), dropped))
    ex = enc[0]
    log("\n===== example 1: NOT trained (prompt) =====")
    log(tok.decode(ex.ids[:ex.n_prompt]))
    log("===== example 1: TRAINED (what the model learns to write) =====")
    log(tok.decode(ex.ids[ex.n_prompt:]))
    log("===== end =====")
    assert ex.ids[-1] == end_id, "the last trained token must be the end token"
    if a.load_model:
        import torch  # noqa
        _, model = load_base(a.model)
        found = adapter_targets(model, a.targets.split(","))
        log("\nlayers that will get adapters:", dict(found), "| total", sum(found.values()))
        missing = [t for t in a.targets.split(",") if t not in found]
        if missing:
            log("WARNING: no Linear layers named", missing)
    log("\nCHECK DONE")


# --------------------------------------------------------------------------------------
# train
# --------------------------------------------------------------------------------------

def cmd_train(a):
    import torch
    import torch.nn.functional as F
    import_peft()
    from peft import LoraConfig, get_peft_model, set_peft_model_state_dict
    from safetensors.torch import load_file

    if not torch.cuda.is_available():
        raise SystemExit("No GPU. Runtime > Change runtime type > T4 GPU.")
    run_dir = os.path.join(a.workdir, "train_runs", a.run_name)
    last_dir = os.path.join(run_dir, "last")
    os.makedirs(run_dir, exist_ok=True)
    data_dir = os.path.join(a.workdir, "train_data", a.data)
    train_path = os.path.join(data_dir, "train.jsonl")
    fp = data_fingerprint(train_path)

    if a.no_thinking:
        open_str, close_str, fmt_note = "", "", "no thinking section (reasoning written as plain text)"
    else:
        open_str, close_str, fmt_note = think_format(a.workdir)
    cfg = {"version": VERSION, "model": a.model, "data": a.data, "data_fingerprint": fp, "peft": a.peft,
           "rank": a.rank, "alpha": a.alpha, "dropout": a.dropout, "targets": a.targets, "lr": a.lr,
           "epochs": a.epochs, "examples_per_step": a.examples_per_step, "tokens_per_micro": a.tokens_per_micro,
           "max_len": a.max_len, "warmup": a.warmup, "weight_decay": a.weight_decay, "clip": a.clip,
           "seed": a.seed, "think_open": open_str, "think_close": close_str, "think_format_note": fmt_note,
           "no_thinking": a.no_thinking, "max_train": a.max_train}
    key = ["model", "data_fingerprint", "peft", "rank", "alpha", "targets", "lr", "epochs", "examples_per_step",
           "tokens_per_micro", "max_len", "seed", "think_open", "think_close", "no_thinking", "max_train"]
    saved = None
    if os.path.exists(os.path.join(run_dir, "config.json")):
        with open(os.path.join(run_dir, "config.json")) as f:
            saved = json.load(f)
        diff = {k: (saved.get(k, KEY_DEFAULTS.get(k)), cfg.get(k)) for k in key
                if saved.get(k, KEY_DEFAULTS.get(k)) != cfg.get(k)}
        if diff:
            raise SystemExit("Run %r already exists with different settings %s.\nUse a new --run-name." % (a.run_name, diff))
    else:
        write_json(os.path.join(run_dir, "config.json"), cfg)

    torch.manual_seed(a.seed)
    random.seed(a.seed)
    log("loading", a.model)
    tok, model = load_base(a.model, "float16")
    end_text, end_id = end_token_text(tok)
    pad_id = tok.pad_token_id if tok.pad_token_id is not None else end_id
    model.config.use_cache = False
    if a.no_grad_ckpt:  # same maths, about a quarter less compute, but every layer keeps its activations
        log("gradient checkpointing OFF (faster; needs more GPU memory)")
    else:
        try:
            model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        except Exception as e:
            log("WARNING: gradient checkpointing unavailable (%s); lower --tokens-per-micro if memory runs out" % e)
    targets = a.targets.split(",")
    found = adapter_targets(model, targets)
    log("adapter layers:", dict(found))
    pcfg = LoraConfig(r=a.rank, lora_alpha=a.alpha, lora_dropout=a.dropout, target_modules=list(found),
                      use_dora=(a.peft == "dora"), bias="none", task_type="CAUSAL_LM")
    model.to("cuda")  # build the adapters on the GPU (DoRA computes weight norms at creation)
    model = get_peft_model(model, pcfg)  # adapter weights are kept in fp32 (PEFT default)
    model.print_trainable_parameters()
    inner = model.get_base_model()

    rows = read_jsonl(train_path)
    if a.max_train and len(rows) > a.max_train:
        rows = random.Random(a.seed).sample(rows, a.max_train)
        log("using a random subset of %d training examples (--max-train)" % len(rows))
    val_rows = read_jsonl(os.path.join(data_dir, "val.jsonl"))
    log("encoding %d training examples ..." % len(rows))
    enc, dropped, _, _ = encode_all(tok, rows, open_str, close_str, end_text, a.max_len, a)
    val_enc, _, _, _ = encode_all(tok, val_rows[:a.val_examples], open_str, close_str, end_text, a.max_len, a)
    log("  %d usable (%d longer than %d tokens dropped); think format: %s" % (len(enc), dropped, a.max_len, fmt_note))
    lengths = [len(e.ids) for e in enc]
    plan = plan_steps(lengths, a.examples_per_step, a.tokens_per_micro, a.epochs, a.seed)
    total = len(plan)
    warm = max(1, int(a.warmup * total))
    log("plan: %d optimizer steps over %d epochs (about %d examples per step)" % (total, a.epochs, a.examples_per_step))

    params = [p for p in model.parameters() if p.requires_grad]
    # DoRA's magnitude vectors are scales: weight decay would shrink them, so they get none.
    decay = [p for n, p in model.named_parameters() if p.requires_grad and "magnitude" not in n]
    no_decay = [p for n, p in model.named_parameters() if p.requires_grad and "magnitude" in n]
    opt = torch.optim.AdamW([{"params": decay, "weight_decay": a.weight_decay},
                             {"params": no_decay, "weight_decay": 0.0}], lr=a.lr, betas=(0.9, 0.999), eps=1e-8)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: lr_factor(s, total, warm))
    scaler = torch.amp.GradScaler("cuda")
    step = 0
    if os.path.exists(os.path.join(last_dir, "trainer_state.pt")):
        state = torch.load(os.path.join(last_dir, "trainer_state.pt"), map_location="cpu", weights_only=False)
        set_peft_model_state_dict(model, load_file(os.path.join(last_dir, "adapter_model.safetensors")))
        opt.load_state_dict(state["opt"])
        sched.load_state_dict(state["sched"])
        scaler.load_state_dict(state["scaler"])
        step = state["step"]
        log("RESUMED from step %d of %d" % (step, total))
    stop_at = min(total, a.max_steps) if a.max_steps else total

    def batch_tensors(idx_list, data):
        L = max(len(data[i].ids) for i in idx_list)
        ids = torch.full((len(idx_list), L), pad_id, dtype=torch.long)
        att = torch.zeros((len(idx_list), L), dtype=torch.long)
        lab = torch.full((len(idx_list), L), -100, dtype=torch.long)
        for r, i in enumerate(idx_list):
            e = data[i]
            n = len(e.ids)
            ids[r, :n] = torch.tensor(e.ids)
            att[r, :n] = 1
            lab[r, e.n_prompt:n] = torch.tensor(e.ids[e.n_prompt:])
        return ids.cuda(), att.cuda(), lab.cuda()

    from torch.utils.checkpoint import checkpoint
    vocab = inner.lm_head.weight.shape[0]
    ce_chunk = max(128, int(2 ** 26 // vocab))  # about 64M logits per chunk (Qwen3.5 vocab 248K -> 270 positions)

    def ce_piece(hh, tt):
        return F.cross_entropy(inner.lm_head(hh).float(), tt, reduction="sum")

    def loss_sum(ids, att, lab):
        """Sum of token losses at trained positions; logits only where they are needed, in chunks that are
        recomputed in the backward pass (a 248K vocabulary would otherwise need gigabytes of logits)."""
        with torch.autocast("cuda", dtype=torch.float16):
            h = inner.model(input_ids=ids, attention_mask=att).last_hidden_state[:, :-1, :]
            tgt = lab[:, 1:]
            sel = tgt != -100
            hs, ts = h[sel], tgt[sel]
            acc = None
            for c in range(0, hs.shape[0], ce_chunk):
                hc, tc = hs[c:c + ce_chunk], ts[c:c + ce_chunk]
                piece = checkpoint(ce_piece, hc, tc, use_reentrant=False) if torch.is_grad_enabled() else ce_piece(hc, tc)
                acc = piece if acc is None else acc + piece
        return acc, int(sel.sum())

    def val_loss():
        model.eval()
        tot, n = 0.0, 0
        mbs = plan_steps([len(e.ids) for e in val_enc], 1, a.tokens_per_micro, 1, 0)
        with torch.no_grad():
            for st in mbs:
                for mb in st["micro"]:
                    s, k = loss_sum(*batch_tensors(mb, val_enc))
                    tot += float(s)
                    n += k
        model.train()
        return tot / max(n, 1)

    def health(n_prompts=8, max_new=a.health_max_new):
        model.eval()
        model.config.use_cache = True
        picks = [r for r in val_rows if r["style"] in ("ug", "math")][:n_prompts]
        prompts = [render_prompt(tok, r["messages"], a) for r in picks]
        texts, finished, lens = [], [], []
        tok.padding_side = "left"
        with torch.no_grad(), torch.autocast("cuda", dtype=torch.float16):
            for s in range(0, len(prompts), 4):
                b = tok(prompts[s:s + 4], return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
                out = model.generate(**b, max_new_tokens=max_new, do_sample=False, eos_token_id=end_id,
                                     pad_token_id=pad_id, use_cache=True)
                for row in out[:, b["input_ids"].shape[1]:].tolist():
                    stop = end_id in row
                    row = row[:row.index(end_id)] if stop else row
                    texts.append(tok.decode(row, skip_special_tokens=False))
                    finished.append(stop)
                    lens.append(len(row))
        tok.padding_side = "right"
        model.config.use_cache = False
        model.train()
        h = format_health(texts, finished, plain=a.no_thinking)
        h["mean_tokens"] = sum(lens) / max(len(lens), 1)
        with open(os.path.join(run_dir, "samples.jsonl"), "a", encoding="utf-8") as f:
            for r, t, fin in zip(picks, texts, finished):
                f.write(json.dumps({"step": step, "id": r["id"], "reference": r["meta"].get("reference"),
                                    "finished": fin, "output": t}, ensure_ascii=False) + "\n")
        return h

    def save(final=False):
        tmp = last_dir + ".tmp"
        if os.path.exists(tmp):
            shutil.rmtree(tmp)
        model.save_pretrained(tmp)
        torch.save({"opt": opt.state_dict(), "sched": sched.state_dict(), "scaler": scaler.state_dict(),
                    "step": step, "time": now()}, os.path.join(tmp, "trainer_state.pt"))
        if os.path.exists(last_dir):
            shutil.rmtree(last_dir)
        os.replace(tmp, last_dir)
        if final or (a.keep_every and step % a.keep_every == 0):
            keep = os.path.join(run_dir, "ckpt-%05d" % step)
            if os.path.exists(keep):
                shutil.rmtree(keep)
            model.save_pretrained(keep)  # adapter only; this is what you evaluate
            log("  kept checkpoint", keep)

    log_path = os.path.join(run_dir, "log.csv")
    new_log = not os.path.exists(log_path)
    logf = open(log_path, "a", newline="")
    w = csv.writer(logf)
    if new_log:
        w.writerow(["time", "step", "epoch", "lr", "train_loss", "grad_norm", "tokens", "sec", "skipped",
                    "val_loss", "closed_thinking", "boxed_after_thinking", "stopped", "mean_tokens"])
    if step == 0 and a.health_every:
        h = health()
        log("health before training (base model):", json.dumps(h))
        w.writerow([now(), 0, 0, 0, "", "", "", "", "", "%.4f" % val_loss(), h["closed_thinking"],
                    h["boxed_after_thinking"], h["stopped"], "%.0f" % h["mean_tokens"]])
        logf.flush()

    model.train()
    t_start, skipped, run_tok, run_loss, run_n = time.time(), 0, 0, 0.0, 0
    win_time, win_n = 0.0, 0
    gpu_total = torch.cuda.get_device_properties(0).total_memory / 2 ** 30
    torch.cuda.reset_peak_memory_stats()
    consecutive_skips = 0
    log("training from step %d to %d" % (step, stop_at))
    while step < stop_at:
        t0 = time.time()
        st = plan[step]
        n_tgt = sum(len(enc[i].ids) - enc[i].n_prompt for mb in st["micro"] for i in mb)
        loss_tot = 0.0
        for mb in st["micro"]:
            try:
                s, k = loss_sum(*batch_tensors(mb, enc))
                scaler.scale(s / n_tgt).backward()
            except torch.cuda.OutOfMemoryError:
                if a.no_grad_ckpt:
                    raise SystemExit("Out of GPU memory. Run again WITHOUT --no-grad-ckpt (same run name; "
                                     "the run continues from its last checkpoint).")
                raise SystemExit("Out of GPU memory. Rerun with a smaller --tokens-per-micro (e.g. 2048); "
                                 "use a new --run-name because the batching changes.")
            loss_tot += float(s.detach())
        scaler.unscale_(opt)
        gn = float(torch.nn.utils.clip_grad_norm_(params, a.clip))
        before = scaler.get_scale()
        scaler.step(opt)
        scaler.update()
        opt.zero_grad(set_to_none=True)
        sched.step()
        step += 1
        was_skipped = scaler.get_scale() < before
        skipped += was_skipped
        consecutive_skips = consecutive_skips + 1 if was_skipped else 0
        if consecutive_skips >= 25:
            save()
            raise SystemExit("25 overflowing steps in a row; training is unstable. Lower --lr and use a new run name.")
        dt = time.time() - t0
        win_time += dt
        win_n += 1
        run_tok += n_tgt
        run_loss += loss_tot
        run_n += 1
        if step % a.log_every == 0 or step == stop_at:
            eta = (stop_at - step) * (time.time() - t_start) / max(run_n, 1) / 3600
            log("[%s] step %d/%d ep %d | loss %.4f | lr %.2e | grad %.2f | %.1f s/step | peak mem %.1f/%.1f GB "
                "| skipped %d | ETA %.1f h"
                % (now()[11:], step, total, st["epoch"] + 1, run_loss / max(run_tok, 1), sched.get_last_lr()[0], gn,
                   win_time / max(win_n, 1), torch.cuda.max_memory_allocated() / 2 ** 30, gpu_total, skipped, eta))
            win_time, win_n = 0.0, 0
            w.writerow([now(), step, st["epoch"] + 1, "%.3e" % sched.get_last_lr()[0], "%.4f" % (run_loss / max(run_tok, 1)),
                        "%.3f" % gn, run_tok, "%.2f" % dt, skipped, "", "", "", "", ""])
            logf.flush()
            run_tok, run_loss = 0, 0.0
        if step % a.val_every == 0 or step == stop_at:
            vl = val_loss()
            log("  validation loss %.4f" % vl)
            w.writerow([now(), step, st["epoch"] + 1, "", "", "", "", "", "", "%.4f" % vl, "", "", "", ""])
            logf.flush()
        if a.health_every and (step % a.health_every == 0 or step == stop_at):
            h = health()
            log("  health:", json.dumps(h))
            w.writerow([now(), step, st["epoch"] + 1, "", "", "", "", "", "", "", h["closed_thinking"],
                        h["boxed_after_thinking"], h["stopped"], "%.0f" % h["mean_tokens"]])
            logf.flush()
        if step % a.save_every == 0 or (a.keep_every and step % a.keep_every == 0) or step == stop_at:
            save(final=(step == total))
        if a.time_budget_min and (time.time() - t_start) / 60 > a.time_budget_min:
            save()
            log("time budget reached at step %d; rerun the same cell to continue" % step)
            break
    logf.close()
    if step >= total:
        log("TRAINING FINISHED. Final adapter: %s" % os.path.join(run_dir, "ckpt-%05d" % step))


# --------------------------------------------------------------------------------------
# sample / merge
# --------------------------------------------------------------------------------------

def cmd_sample(a):
    import torch
    import_peft()
    from peft import PeftModel
    tok, model = load_base(a.model, "float16")
    model = model.cuda()  # merge on the GPU (fp16 norms are not supported on every CPU build)
    if a.adapter:
        model = PeftModel.from_pretrained(model, a.adapter).merge_and_unload()
    model = model.eval()
    end_text, end_id = end_token_text(tok)
    rows = read_jsonl(os.path.join(a.workdir, "train_data", a.data, "val.jsonl"))
    rnd = random.Random(a.seed)
    for r in rnd.sample(rows, min(a.n, len(rows))):
        p = render_prompt(tok, r["messages"], a)
        b = tok(p, return_tensors="pt", add_special_tokens=False).to("cuda")
        with torch.no_grad():
            out = model.generate(**b, max_new_tokens=a.max_new_tokens, do_sample=False, eos_token_id=end_id)
        text = tok.decode(out[0, b["input_ids"].shape[1]:], skip_special_tokens=False)
        log("\n" + "=" * 80 + "\nQUESTION (%s): %s\nREFERENCE: %s\n--- OUTPUT (%d tokens) ---\n%s"
            % (r["style"], r["messages"][-1]["content"][-600:], r["meta"].get("reference"),
               out.shape[1] - b["input_ids"].shape[1], text))


def cmd_merge(a):
    import_peft()
    from peft import PeftModel
    import torch
    on_gpu = torch.cuda.is_available()
    tok, model = load_base(a.model, "float16" if on_gpu else "float32")
    if on_gpu:
        model = model.cuda()
    model = PeftModel.from_pretrained(model, a.adapter).merge_and_unload()
    model = model.to(torch.float16)
    model.save_pretrained(a.out, safe_serialization=True)
    tok.save_pretrained(a.out)
    log("merged model saved to", a.out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--workdir", required=True)
        p.add_argument("--data", default="v1")
        p.add_argument("--model", default=MODEL_ID)
        p.add_argument("--max-len", type=int, default=2048)
        p.add_argument("--seed", type=int, default=3407)
        p.add_argument("--no-thinking", action="store_true",
                       help="non-thinking mode (Qwen3.5): prompt rendered with enable_thinking=False, reasoning trained "
                            "as plain text before the boxed answer")
        return p

    p = common(sub.add_parser("check"))
    p.add_argument("--targets", default="auto", help="comma-separated layer names; auto = the list for the model")
    p.add_argument("--load-model", action="store_true", help="also load the model on CPU to list adapter layers")
    p.set_defaults(fn=cmd_check)

    p = common(sub.add_parser("train"))
    p.add_argument("--run-name", required=True)
    p.add_argument("--peft", choices=["dora", "lora"], default="dora")
    p.add_argument("--rank", type=int, default=32)
    p.add_argument("--alpha", type=int, default=64)
    p.add_argument("--dropout", type=float, default=0.0, help="0 lets DoRA reuse the base layer output (faster)")
    p.add_argument("--targets", default="auto", help="comma-separated layer names; auto = the list for the model")
    p.add_argument("--max-train", type=int, default=0, help="train on a fixed random subset of N examples (0 = all)")
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--epochs", type=int, default=2)
    p.add_argument("--examples-per-step", type=int, default=16)
    p.add_argument("--tokens-per-micro", type=int, default=4096)
    p.add_argument("--no-grad-ckpt", action="store_true",
                   help="turn gradient checkpointing off: faster, more memory (can be switched between sessions)")
    p.add_argument("--warmup", type=float, default=0.05)
    p.add_argument("--weight-decay", type=float, default=0.01)
    p.add_argument("--clip", type=float, default=1.0)
    p.add_argument("--max-steps", type=int, default=0, help="stop early (pilot runs)")
    p.add_argument("--log-every", type=int, default=10)
    p.add_argument("--val-every", type=int, default=200)
    p.add_argument("--val-examples", type=int, default=200)
    p.add_argument("--health-every", type=int, default=600, help="0 turns the generation check off")
    p.add_argument("--health-max-new", type=int, default=1536, help="token budget of the generation check")
    p.add_argument("--save-every", type=int, default=200)
    p.add_argument("--keep-every", type=int, default=600, help="keep an evaluable checkpoint every N steps")
    p.add_argument("--time-budget-min", type=float, default=0)
    p.set_defaults(fn=cmd_train)

    p = common(sub.add_parser("sample"))
    p.add_argument("--adapter")
    p.add_argument("--n", type=int, default=3)
    p.add_argument("--max-new-tokens", type=int, default=2048)
    p.set_defaults(fn=cmd_sample)

    p = common(sub.add_parser("merge"))
    p.add_argument("--adapter", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_merge)

    a = ap.parse_args(argv)
    if hasattr(a, "targets"):
        a.targets = resolve_targets(a)
    a.fn(a)


if __name__ == "__main__":
    main()
