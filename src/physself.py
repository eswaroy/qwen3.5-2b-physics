#!/usr/bin/env python3
"""
physself.py - Phase 3b: self-distillation data for LFM2.5-1.2B-Thinking.

Why this exists. Training on short teacher traces (data v1.2, median 480 thinking tokens) taught the model to
finish its answers, but it replaced the model's own long reasoning: on the same questions, the step-600 LoRA
checkpoint scored 5.5% on UGPhysics (base 13.3%) and 46.8% on MATH-500 (base 67.5%).

So here the BASE model answers our training questions (already decontaminated, with reference answers) in its
own thinking style. We keep only answers that finish within the token budget and that the official UGPhysics
grader marks correct, and per question the SHORTEST correct one. Fine-tuning on these keeps the model's way of
thinking, teaches it to finish and box its answer, and shows it only correct reasoning (rejection-sampling
fine-tuning; self-training on the shortest correct samples shortens outputs without losing accuracy).

Commands
  select    (CPU, once)        pick balanced questions with checkable answers -> selfgen/<name>/questions.jsonl
  generate  (GPU, per account) answer one shard of the questions; resumable; backends vllm (fast), hf, mock
  status    (any)              progress of every shard
  build     (CPU, once)        grade all answers, keep the shortest correct one per question -> train_data/<out>/

Needs physeval.py (1.3+) and physdata.py (1.2+) in the same folder.
"""
import argparse
import collections
import csv
import glob
import hashlib
import json
import math
import os
import random
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import physeval as PE  # noqa: E402
import physdata as D  # noqa: E402

VERSION = "1.2"
SEED = 20261009
MODEL_ID = "LiquidAI/LFM2.5-1.2B-Thinking"


def log(*a):
    print(*a, flush=True)


def sha(s):
    return hashlib.sha1(s.encode("utf-8", "replace")).hexdigest()


def qdir(a):
    return os.path.join(a.workdir, "selfgen", a.name)


def label(q):
    return "maths" if q["style"] == "math" else (q.get("topic") or "untagged")


# --------------------------------------------------------------------------------------
# select
# --------------------------------------------------------------------------------------

def gold_of(answer):
    boxes = D.boxed_contents(answer or "")
    return boxes[-1][2].strip() if boxes else ""


def plain_prompt(messages):
    """The bare question with the simple maths-style instruction, for GENERATING answers.

    With the official UGPhysics prompt ("end your solution with 'So the final answer is \\boxed{answer}(unit)',
    no unit in the box") the base model spends much of its thinking arguing about the format, and often closes its
    thinking, writes an answer, reopens it and closes it again. Generating with this simple prompt and training
    with the official one (answer line rewritten to the official format) teaches it to answer the official prompt
    with clean reasoning (context distillation)."""
    user = messages[-1]["content"]
    if user.startswith("The following is an open-ended problem") and "\n\n" in user:
        return [{"role": "user", "content": user.split("\n\n", 1)[1].strip() + PE.MATH_SUFFIX}]
    return None


def interleave(groups, rnd):
    """groups: {key: [items in priority order]}. One order in which every prefix keeps the groups' proportions."""
    keyed = []
    for g, items in groups.items():
        n = max(len(items), 1)
        for i, it in enumerate(items):
            keyed.append(((i + rnd.random()) / n, it))
    keyed.sort(key=lambda x: x[0])
    return [it for _, it in keyed]


def cmd_select(a):
    wd = a.workdir
    rnd = random.Random(SEED)
    src = os.path.join(wd, "train_data", a.source)
    rows = PE.read_jsonl(os.path.join(src, "train.jsonl")) + PE.read_jsonl(os.path.join(src, "val.jsonl"))
    if not rows:
        raise SystemExit("no data in %s - build it with PhysicsData.ipynb first" % src)
    ug_items = PE.read_jsonl(os.path.join(wd, "data", "items_ugphysics.jsonl"))
    share, exam, acc, note = D.subject_targets(wd, ug_items)
    cands, skipped = [], collections.Counter()
    for r in rows:
        if r["style"] not in ("ug", "knowledge", "math"):
            skipped["free-form style (%s)" % r["style"]] += 1
            continue
        gold = gold_of(r["answer"])
        if not gold:
            skipped["no boxed reference"] += 1
            continue
        m = r.get("meta", {})
        cands.append({"id": r["id"], "style": r["style"], "messages": r["messages"], "gold": gold,
                      "atype": m.get("answer_type"), "topic": m.get("topic"), "check": m.get("check"),
                      "source": r.get("source")})
    log("questions with a checkable reference: %d (skipped %s)" % (len(cands), dict(skipped)))

    def weight(c):
        w = 1.5 if c["check"] in ("agrees", "agrees after normalising") else 1.0  # reference confirmed twice
        if c["atype"] in ("EX", "EQ") or "," in (c["atype"] or ""):
            w *= 1.2
        if c["style"] == "knowledge":
            w *= 0.6  # multiple choice: easy to guess right, so less informative
        return w

    phys = [c for c in cands if c["style"] != "math"]
    maths = [c for c in cands if c["style"] == "math"]
    n_math = min(len(maths), int(round(a.n * a.math_share)))
    n_phys = min(len(phys), a.n - n_math)
    strata = collections.defaultdict(list)
    for c in D.priority_order(phys, weight, rnd):
        strata[c["topic"]].append(c)
    sh = {k: share.get(k, 0.03 if k is None else 0.0) for k in strata}
    quota = D.waterfill(n_phys, sh, {k: len(v) for k, v in strata.items()})
    groups = {k: strata[k][:quota[k]] for k in strata if quota.get(k)}
    groups["__math__"] = D.priority_order(maths, weight, rnd)[:n_math]
    order = interleave(groups, rnd)
    n_plain = 0
    for q in order:
        if a.gen_prompt == "plain" and q["style"] != "math":
            gm = plain_prompt(q["messages"])
            if gm:
                q["gen_messages"] = gm
                n_plain += 1
    out_dir = qdir(a)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "questions.jsonl")
    if os.path.exists(path) and not a.force:
        raise SystemExit("%s exists. Use --force to replace it (only before any generation started)." % path)
    for i, q in enumerate(order):
        q["order"] = i
    PE.write_jsonl(path, order)
    by = collections.Counter(label(q) for q in order)
    md = ["# Self-distillation questions: %s\n" % a.name,
          "Selected %s from data %s: %d questions (%d physics, %d maths). %s.\n"
          % (PE.now(), a.source, len(order), n_phys, n_math, note),
          "Questions are in an interleaved order: any first part of the list keeps these proportions, so a run "
          "that stops early is still balanced.\n",
          "Generation prompt: %s (%d questions are answered with the simple prompt and trained with the official one).\n"
          % (a.gen_prompt, n_plain),
          "| subject | questions | share | exam share |", "|---|---|---|---|"]
    for k, v in by.most_common():
        md.append("| %s | %d | %.1f%% | %s |" % (k, v, 100.0 * v / len(order),
                                               "%.1f%%" % (100 * exam[k]) if k in exam else "-"))
    md.append("\n| style | questions |\n|---|---|")
    md += ["| %s | %d |" % kv for kv in collections.Counter(q["style"] for q in order).most_common()]
    with open(os.path.join(out_dir, "select.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    log("\n".join(md))
    log("\nwrote %s" % path)


# --------------------------------------------------------------------------------------
# generate
# --------------------------------------------------------------------------------------

def gen_cfg(a):
    return {"model": a.model, "temperature": a.temperature, "top_p": a.top_p, "top_k": a.top_k,
            "repetition_penalty": a.repetition_penalty, "max_new_tokens": a.max_new_tokens}


def gen_key(cfg):
    return sha(json.dumps(cfg, sort_keys=True))[:10]


class HFGen:
    """Batched generation with transformers (always works; slower). Loop detection stops runaway rows early."""

    def __init__(self, a):
        cfg = dict(gen_cfg(a), dtype=None, template_kwargs={}, loop_stop=True, adapter=None)
        self.be = PE.HFBackend(cfg)
        self.batch = a.batch_size
        self.name = "hf"

    def run(self, pairs):
        """pairs: [(question, sample_index)] -> list of result dicts (same order)."""
        texts = [self.be.render(q.get("gen_messages") or q["messages"]) for q, _ in pairs]
        out, i = [], 0
        while i < len(texts):
            chunk = texts[i:i + self.batch]
            try:
                res = self.be.generate(chunk)
            except Exception as e:
                if not self.be.is_oom(e) or self.batch <= 1:
                    raise
                self.be.free()
                self.batch = max(1, self.batch // 2)
                log("  out of GPU memory: batch size lowered to %d" % self.batch)
                continue
            out += res
            i += len(chunk)
        return out


class VLLMGen:
    """vLLM offline engine: continuous batching, several times faster than transformers on a T4."""

    def __init__(self, a):
        from vllm import LLM, SamplingParams
        self.SP = SamplingParams
        self.a = a
        self.llm = LLM(model=a.model, dtype="half", max_model_len=a.max_model_len, seed=PE.SEED,
                       gpu_memory_utilization=a.gpu_memory_utilization, enable_prefix_caching=True)
        self.tok = self.llm.get_tokenizer()
        self.name = "vllm"

    def run(self, pairs):
        a = self.a
        prompts, params = [], []
        for q, k in pairs:
            text = self.tok.apply_chat_template(q.get("gen_messages") or q["messages"], tokenize=False,
                                                add_generation_prompt=True)
            # token ids, so vLLM does not add a second start-of-text token to the rendered template
            prompts.append({"prompt_token_ids": self.tok(text, add_special_tokens=False)["input_ids"]})
            kw = dict(temperature=a.temperature, max_tokens=a.max_new_tokens, repetition_penalty=a.repetition_penalty,
                      skip_special_tokens=False, spaces_between_special_tokens=False,
                      seed=int(sha("%s/%d" % (q["id"], k))[:8], 16))
            if a.temperature > 0 and a.top_p:
                kw["top_p"] = a.top_p
            if a.temperature > 0 and a.top_k:
                kw["top_k"] = a.top_k
            params.append(self.SP(**kw))
        outs = self.llm.generate(prompts, params, use_tqdm=False)
        res = []
        for o in outs:
            c = o.outputs[0]
            ids = list(c.token_ids)
            reason = "stop" if c.finish_reason == "stop" else "length"
            if reason == "length" and PE.detect_loop(ids[-512:]):
                reason = "loop"
            text = c.text
            for t in ("<|im_end|>", "<|endoftext|>", "<|startoftext|>"):
                text = text.replace(t, "")
            res.append({"text": text, "n_new_tokens": len(ids), "finish_reason": reason,
                        "n_prompt_tokens": len(o.prompt_token_ids or [])})
        return res


class MockGen:
    """No GPU: fabricated answers for testing the pipeline. Never use for real data."""

    def __init__(self, a):
        self.a, self.name = a, "mock"

    def run(self, pairs):
        res = []
        for q, k in pairs:
            rnd = random.Random(sha("%s/%d" % (q["id"], k)))
            think = "Let me work through the physics carefully. " * rnd.randint(5, 120)
            u = rnd.random()
            if u < 0.15:
                text, reason = "<think>" + think * 3, "length"
            elif u < 0.18:
                text, reason = "<think>" + think + "x = 1 " * 300, "loop"
            else:
                right = rnd.random() < 0.45
                ans = q["gold"] if right else "42.5"
                text, reason = "<think>%s</think>\n\nSo the final answer is \\boxed{%s}." % (think, ans), "stop"
            res.append({"text": text, "n_new_tokens": len(text) // 4, "finish_reason": reason,
                        "n_prompt_tokens": 200})
        return res


def shard_file(a, shard):
    return os.path.join(qdir(a), "gen_shard%d.jsonl" % shard)


def cmd_generate(a):
    questions = PE.read_jsonl(os.path.join(qdir(a), "questions.jsonl"))
    if not questions:
        raise SystemExit("no questions - run the select step first")
    mine = [q for q in questions if q["order"] % a.num_shards == a.shard]
    cfg = gen_cfg(a)
    key = gen_key(cfg)
    out = shard_file(a, a.shard)
    done = collections.Counter()
    for r in PE.read_jsonl(out):
        if r.get("gen_key") == key:
            done[r["id"]] += 1
    todo = [(q, k) for q in mine for k in range(done[q["id"]], a.samples)]
    if a.limit:
        todo = todo[:a.limit]
    log("shard %d of %d: %d questions, %d answers already done with these settings, %d to do"
        % (a.shard, a.num_shards, len(mine), sum(done.values()), len(todo)))
    if not todo:
        log("Nothing left to do for this shard.")
        return
    backend = {"hf": HFGen, "vllm": VLLMGen, "mock": MockGen}[a.backend](a)
    t0, n_tok, n_rows = time.time(), 0, 0
    reasons = collections.Counter()
    chunk = a.chunk if a.backend == "vllm" else a.batch_size  # results are saved after every chunk
    for s in range(0, len(todo), chunk):
        part = todo[s:s + chunk]
        res = backend.run(part)
        rows = []
        for (q, k), r in zip(part, res):
            rows.append({"id": q["id"], "sample": k, "gen_key": key, "backend": backend.name, "text": r["text"],
                         "n_new_tokens": r["n_new_tokens"], "finish_reason": r["finish_reason"],
                         "n_prompt_tokens": r.get("n_prompt_tokens")})
            n_tok += r["n_new_tokens"]
        PE.append_jsonl(out, rows)
        n_rows += len(rows)
        el = time.time() - t0
        reasons.update(r["finish_reason"] for r in rows)
        log("[%s] %d/%d answers | %.0f tok/s | avg %.0f new tok | %s | ETA %.1f h"
            % (PE.now()[11:], n_rows, len(todo), n_tok / max(el, 1e-6), n_tok / max(n_rows, 1), dict(reasons),
               (len(todo) - n_rows) * el / max(n_rows, 1) / 3600))
        if a.time_budget_min and el / 60 > a.time_budget_min:
            log("time budget reached; run the same cell again later to continue")
            break
    log("Done for now: %d answers, %d new tokens in %.2f GPU-hours." % (n_rows, n_tok, (time.time() - t0) / 3600))


def cmd_status(a):
    questions = PE.read_jsonl(os.path.join(qdir(a), "questions.jsonl"))
    log("%d questions in %s" % (len(questions), qdir(a)))
    for path in sorted(glob.glob(os.path.join(qdir(a), "gen_shard*.jsonl"))):
        rows = PE.read_jsonl(path)
        ids = {r["id"] for r in rows}
        reasons = collections.Counter(r["finish_reason"] for r in rows)
        toks = [r["n_new_tokens"] for r in rows]
        log("%s: %d answers for %d questions | %s | median %d new tokens"
            % (os.path.basename(path), len(rows), len(ids), dict(reasons), PE.quantile(toks, .5) if toks else 0))


# --------------------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------------------

FORMAT_TALK = re.compile(
    r"\bthe user (?:said|says|wants|asked|mentioned|specified|instructed|instructions?)\b|\bthe instructions?\b"
    r"|\(unit\)|\bunits? (?:should|shouldn't|should not|must not)\b|\b(?:inside|in) the box\b|\bboxed format\b", re.I)
RAMBLE = re.compile(r"\b(?:Wait|Hmm|Alternatively|Actually|Let me (?:check|verify|re))\b")


def last_box(text):
    b = D.boxed_contents(text)
    return b[-1][2].strip() if b else ""


def clean_answer(ans):
    """Cut the answer after the first line that states the final boxed answer (drops repeats and later chatter).
    The final boxed answer itself is unchanged, so the grade stays valid."""
    final = D.latex_norm(last_box(ans))
    lines = ans.split("\n")
    for i, line in enumerate(lines):
        if any(D.latex_norm(b[2].strip()) == final for b in D.boxed_contents(line)):
            end = i + 1
            if end < len(lines) and lines[end].strip() in ("\\]", "$$"):
                end += 1
            return "\n".join(lines[:end]).strip()
    return ans.strip()


def lhs_norm(s):
    """latex_norm that also treats "\\dot q" like "\\dot{q}"."""
    return D.latex_norm(re.sub(r"\\([A-Za-z]+)\s+([A-Za-z0-9])", r"\\\1{\2}", s))


def answer_in_question(gold, question):
    g = D.latex_norm(gold)
    return len(g) >= 6 and g in D.latex_norm(question)


def equation_pairs(pred, gold):
    """For equation answers: the (predicted, reference) left-hand sides that must also agree. None = shapes differ.
    The official judge can accept an equation whose right-hand side matches but whose left-hand side is a
    different quantity, so equations get this extra check."""
    gp, pp = D.split_top_level(gold), D.split_top_level(pred)
    if len(gp) != len(pp):
        return None
    out = []
    for g, p_ in zip(gp, pp):
        if "=" not in g:
            continue
        if "=" not in p_:
            return None
        out.append((p_.split("=", 1)[0].strip(), g.split("=", 1)[0].strip()))
    return out


def final_answer(ans, atype):
    """The answer the grader sees: the last box, or the last n boxes joined for an n-part answer."""
    boxes = [b[2].strip() for b in D.boxed_contents(ans)]
    if not boxes:
        return ""
    n = (atype or "").count(",") + 1
    if n > 1 and len(boxes) >= n and len(D.split_top_level(boxes[-1])) < n:
        f = ", ".join(boxes[-n:])
    else:
        f = boxes[-1]
    m = re.fullmatch(r"\\text\s*\{([^{}]*)\}", f)
    return m.group(1).strip() if m else f


def unit_after_box(ans):
    """'... \\boxed{4} W.' -> 'W' (a unit written right after the final box), else ''."""
    spans = D.boxed_contents(ans)
    if not spans:
        return ""
    i, j, inner = spans[-1]
    tail = re.sub(r"^[\s$]*(?:\\[,;! ]\s*)*", "", ans[j:].split("\n")[0])
    m = re.match(r"(\\(?:text|mathrm)\s*\{[^{}]{1,15}\}|[A-Za-z\u03a9\u03bc\u00b0][A-Za-z0-9/^\-\u03a9\u03bc\u00b0 ]{0,14}?)(?=[\s$]*(?:[.,;]|$))", tail)
    if not m:
        return ""
    nu = D.split_number_unit(inner.strip() + " " + m.group(1))
    return nu[1] if nu and nu[1] else ""


def official_answer(ans, final, question):
    """Rewrite an answer written for the simple prompt into the official UGPhysics ending:
    the model's own short explanation, then 'So the final answer is \\boxed{...} unit.' (unit outside the box)."""
    t, items, units = D.classify(final, question)
    if not items:
        items, units = [final], [""]
    if t == "NV" and not units[0]:
        units = [unit_after_box(ans)]
    line = D.answer_line(items, units, len(items) > 1)
    out = []
    for l in ans.split("\n"):
        if "\\boxed" in l:
            continue
        if out and out[-1].strip() in ("\\[", "$$") and l.strip() in ("\\]", "$$"):
            out.pop()  # an emptied display block
            continue
        out.append(l)
    heading = re.compile(r"\**\s*(?:the\s+)?final answer\s*:?\s*\**\s*:?", re.I)
    while out and (out[-1].strip() in ("", "\\[", "\\]", "$$") or heading.fullmatch(out[-1].strip())):
        out.pop()
    text = "\n".join(out).strip()
    return (text + "\n\n" if text else "") + line


def cmd_build(a):
    wd = a.workdir
    qs = {q["id"]: q for q in PE.read_jsonl(os.path.join(qdir(a), "questions.jsonl"))}
    rows = []
    for path in sorted(glob.glob(os.path.join(qdir(a), "gen_shard*.jsonl"))):
        rows += PE.read_jsonl(path)
    if not rows:
        raise SystemExit("no generated answers yet")
    log("1/4 %d answers for %d questions" % (len(rows), len({r["id"] for r in rows})))

    log("2/4 basic checks (finished, thinking closed, boxed answer after the thinking, length)")
    why = collections.Counter()
    graded = []
    for r in rows:
        q = qs.get(r["id"])
        if q is None:
            why["question not in the current list"] += 1
            continue
        think, ans, closed = PE.split_thinking(r["text"], False)
        r["_think"], r["_ans"] = think, ans
        r["_final"] = final_answer(ans, q["atype"])
        if r["finish_reason"] != "stop":
            why["did not finish (%s)" % r["finish_reason"]] += 1
        elif not closed or len(think) < 50:
            why["no complete thinking section"] += 1
        elif "\\boxed" not in ans:
            why["no boxed answer after the thinking"] += 1
        elif r["n_new_tokens"] > a.max_new_tokens:
            why["longer than %d tokens" % a.max_new_tokens] += 1
        elif len(ans) > a.max_answer_chars:
            why["answer section too long"] += 1
        elif r["text"].count("</think>") > 1 or r["text"].count("<think>") > 1:
            why["closed its thinking more than once"] += 1
        elif answer_in_question(q["gold"], q["messages"][-1]["content"]):
            why["the answer is given in the question (nothing to solve)"] += 1
        else:
            graded.append(r)
    log("  %d of %d pass; %s" % (len(graded), len(rows), dict(why)))

    log("3/4 grading with the official UGPhysics rule judge")
    PE.ensure_repos()
    cache = D.GraderCache(os.path.join(qdir(a), "grade_cache.jsonl"))
    tasks, keys, queued = [], [], set()
    for r in graded:
        gold = "\\boxed{%s}" % qs[r["id"]]["gold"]
        k = sha("\\boxed{%s}\x00%s" % (r["_final"], gold))
        r["_key"] = k
        if cache.get(k) is None and k not in queued:
            tasks.append({"workdir": wd, "answer": "\\boxed{%s}" % r["_final"], "gold": gold,
                          "precision": PE.UG_PRECISION, "try_units": True})
            keys.append(k)
            queued.add(k)
    if tasks:
        pool = PE.GradePool(a.workers, 60)
        res = pool.map(tasks, progress=2000)
        pool.close()
        for k, r in zip(keys, res):
            cache.put(k, bool(r["rule"] or r["rule_units"]))
        cache.flush()
    for r in graded:
        r["_ok"] = bool(cache.get(r["_key"]))
    judged = [r for r in graded if r["_ok"]]
    log("  %d judged correct of %d graded (%d answers in total)" % (len(judged), len(graded), len(rows)))

    log("    stricter checks: equation left-hand sides, clean ending, talk about the answer format")
    eq_tasks, eq_keys, queued = [], [], set()
    for r in judged:
        gold = qs[r["id"]]["gold"]
        r["_eq"] = None
        if "=" in gold:
            pairs = equation_pairs(r["_final"], gold)
            r["_eq"] = pairs if pairs is not None else "shape"
            for pl, gl in (pairs or []):
                if lhs_norm(pl) == lhs_norm(gl):
                    continue
                k = sha("\\boxed{%s}\x00\\boxed{%s}" % (pl, gl))
                if cache.get(k) is None and k not in queued:
                    eq_tasks.append({"workdir": wd, "answer": "\\boxed{%s}" % pl, "gold": "\\boxed{%s}" % gl,
                                     "precision": PE.UG_PRECISION, "try_units": False})
                    eq_keys.append(k)
                    queued.add(k)
    if eq_tasks:
        pool = PE.GradePool(a.workers, 60)
        res = pool.map(eq_tasks, progress=2000)
        pool.close()
        for k, r in zip(eq_keys, res):
            cache.put(k, bool(r["rule"]))
        cache.flush()
    talk = []
    correct = []
    for r in judged:
        if r["_eq"] == "shape":
            why["equation answer has a different shape than the reference"] += 1
            continue
        if r["_eq"] and not all(lhs_norm(pl) == lhs_norm(gl) or cache.get(sha("\\boxed{%s}\x00\\boxed{%s}" % (pl, gl)))
                                for pl, gl in r["_eq"]):
            why["equation for a different quantity (left-hand side differs)"] += 1
            continue
        r["_ans"] = clean_answer(r["_ans"])
        q = qs[r["id"]]
        if q.get("gen_messages"):  # answered with the simple prompt: end it the official way
            r["_ans"] = official_answer(r["_ans"], r["_final"], q["messages"][-1]["content"])
        if RAMBLE.search(r["_ans"]):
            why["keeps thinking after the thinking section"] += 1
            continue
        r["_talk"] = len(FORMAT_TALK.findall(r["_think"]))
        talk.append(r["_talk"])
        if r["_talk"] >= a.max_format_talk:
            why["talks about the answer format %d+ times" % a.max_format_talk] += 1
            continue
        correct.append(r)
    log("  %d correct answers pass the stricter checks" % len(correct))

    log("4/4 choosing the shortest correct answer per question")
    best = {}
    for r in correct:
        b = best.get(r["id"])
        if b is None or (r["n_new_tokens"], r["sample"]) < (b["n_new_tokens"], b["sample"]):
            best[r["id"]] = r
    n_correct = collections.Counter(r["id"] for r in correct)
    n_samples = collections.Counter(r["id"] for r in rows)
    examples = []
    for qid, r in best.items():
        q = qs[qid]
        examples.append({"id": "self/%s" % qid, "source": "self_" + (q.get("source") or "?"), "style": q["style"],
                         "messages": q["messages"], "think": r["_think"], "answer": r["_ans"],
                         "meta": {"answer_type": q["atype"], "topic": q["topic"], "reference": q["gold"][:400],
                                  "check": "self-generated, graded correct", "n_samples": n_samples[qid],
                                  "n_correct": n_correct[qid], "sample_new_tokens": r["n_new_tokens"],
                                  "format_talk": r["_talk"],
                                  "tokens": {"prompt": r.get("n_prompt_tokens") or 0,
                                             "think": int(r["n_new_tokens"] * len(r["_think"]) / max(len(r["text"]), 1)),
                                             "answer": int(r["n_new_tokens"] * len(r["_ans"]) / max(len(r["text"]), 1))}}})
    added = []
    if a.add_from:
        have = {e["id"] for e in examples}
        styles = set(a.add_styles.split(","))
        src = os.path.join(wd, "train_data", a.add_from)
        for e in PE.read_jsonl(os.path.join(src, "train.jsonl")) + PE.read_jsonl(os.path.join(src, "val.jsonl")):
            if e["style"] in styles and e["id"] not in have:
                added.append(e)
        log("  added %d examples (%s) from train_data/%s" % (len(added), a.add_styles, a.add_from))
        examples += added
    rnd = random.Random(SEED)
    rnd.shuffle(examples)
    n_val = min(a.n_val, len(examples) // 10)
    val, train = examples[:n_val], examples[n_val:]
    out = os.path.join(wd, "train_data", a.out)
    os.makedirs(out, exist_ok=True)
    PE.write_jsonl(os.path.join(out, "train.jsonl"), train)
    PE.write_jsonl(os.path.join(out, "val.jsonl"), val)
    hard = [q for qid, q in qs.items() if n_samples[qid] and not n_correct[qid]]
    PE.write_jsonl(os.path.join(qdir(a), "hard_questions.jsonl"), hard)
    write_self_stats(out, a, rows, graded, correct, best, qs, train, val, why, hard, judged, talk, added)
    write_self_samples(out, train, rnd)
    log("\nDONE: %d training and %d validation examples in %s" % (len(train), len(val), out))


def write_self_stats(out, a, rows, graded, correct, best, qs, train, val, why, hard, judged, talk, added=()):
    q = lambda xs, p: PE.quantile(xs, p) if xs else 0
    by_topic = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        if r["id"] not in qs:
            continue
        t = label(qs[r["id"]])
        by_topic[t]["answers"] += 1
        by_topic[t]["finished"] += r["finish_reason"] == "stop"
    for r in correct:
        by_topic[label(qs[r["id"]])]["correct"] += 1
    asked = collections.Counter(label(qs[i]) for i in {r["id"] for r in rows} if i in qs)
    chosen = collections.Counter(label(qs[i]) for i in best)
    all_tok = [r["n_new_tokens"] for r in rows]
    fin_tok = [r["n_new_tokens"] for r in rows if r["finish_reason"] == "stop"]
    cor_tok = [r["n_new_tokens"] for r in correct]
    best_tok = [r["n_new_tokens"] for r in best.values()]
    n_q = len({r["id"] for r in rows})
    md = ["# Self-distillation data %s\n" % a.out,
          "Built %s with physself.py %s from selfgen/%s. %d training and %d validation examples.\n"
          % (PE.now(), VERSION, a.name, len(train), len(val)),
          "## Overview\n",
          "| | value |", "|---|---|",
          "| questions answered | %d |" % n_q,
          "| answers generated | %d |" % len(rows),
          "| finished normally | %.1f%% |" % (100.0 * len(fin_tok) / max(len(rows), 1)),
          "| judged correct by the official rule judge (per answer) | %.1f%% |" % (100.0 * len(judged) / max(len(rows), 1)),
          "| correct and clean (passed the stricter checks) | %.1f%% |" % (100.0 * len(correct) / max(len(rows), 1)),
          "| questions with at least one correct answer | %.1f%% |" % (100.0 * len(best) / max(n_q, 1)),
          "| examples kept (one per question) | %d |" % len(best),
          "| examples added from %s (%s) | %d |" % (a.add_from or "-", a.add_styles if a.add_from else "-", len(added)),
          "| answered with the simple prompt, trained with the official one | %d |"
          % sum(1 for i in best if qs[i].get("gen_messages")),
          "\n## Lengths (new tokens)\n", "| answers | median | p90 | max |", "|---|---|---|---|"]
    for name, xs in (("all", all_tok), ("finished", fin_tok), ("correct", cor_tok), ("kept (shortest correct)", best_tok)):
        md.append("| %s | %.0f | %.0f | %d |" % (name, q(xs, .5), q(xs, .9), max(xs) if xs else 0))
    md += ["\nThe base model's median on UGPhysics was 4,096 (the limit). Every kept example finishes, so the "
           "model learns to finish in its own style.\n",
           "## By subject\n",
           "| subject | questions | answers | finished | correct per answer | kept |", "|---|---|---|---|---|---|"]
    for t, c in sorted(by_topic.items(), key=lambda x: -x[1]["answers"]):
        md.append("| %s | %d | %d | %.0f%% | %.0f%% | %d |" % (t, asked[t], c["answers"], 100.0 * c["finished"] / max(c["answers"], 1),
                                                        100.0 * c["correct"] / max(c["answers"], 1), chosen[t]))
    md += ["\n## Styles kept\n", "| style | examples |", "|---|---|"]
    md += ["| %s | %d |" % kv for kv in collections.Counter(e["style"] for e in train + val).most_common()]
    md += ["\n## Talk about the answer format in the thinking\n",
           "How often a judged-correct answer's thinking discusses the answer format (\"the user said\", \"(unit)\", "
           "\"in the box\" ...). Answers with %d or more mentions are dropped (--max-format-talk).\n" % a.max_format_talk,
           "| mentions | answers |", "|---|---|"]
    for lo, hi in ((0, 0), (1, 3), (4, 7), (8, 11), (12, 10 ** 9)):
        md.append("| %s | %d |" % (("%d" % lo) if lo == hi else ("%d+" % lo if hi > 10 ** 8 else "%d-%d" % (lo, hi)),
                                   sum(1 for t in talk if lo <= t <= hi)))
    md += ["\n## Not kept\n"] + ["- %s: %d" % kv for kv in why.most_common()] + [
        "\n%d questions had no correct answer (saved in selfgen/%s/hard_questions.jsonl for a later round)." % (len(hard), a.name),
        "\n## Settings\n", "```", json.dumps({k: v for k, v in vars(a).items() if k != "fn"}, indent=1, default=str), "```"]
    with open(os.path.join(out, "stats.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")


def write_self_samples(out, train, rnd):
    by = collections.defaultdict(list)
    for e in train:
        by[e["style"]].append(e)
    md = ["# Samples (2 per style)\n", "The base model's own answers that were graded correct. Thinking is cut at "
          "3,000 characters here only.\n"]
    for s, items in sorted(by.items()):
        for e in rnd.sample(items, min(2, len(items))):
            md.append("---\n## %s | %s | %s | %d tokens | format talk %d\n" % (
                s, e["meta"]["topic"], e["meta"]["answer_type"], e["meta"]["sample_new_tokens"], e["meta"]["format_talk"]))
            md.append("**user:**\n```\n%s\n```" % e["messages"][-1]["content"][-1500:])
            md.append("**reference:** `%s`\n" % e["meta"]["reference"])
            th = e["think"]
            th = th if len(th) <= 3000 else th[:1500] + "\n[...]\n" + th[-1500:]
            md.append("**assistant:**\n```\n<think>\n%s\n</think>\n\n%s\n```\n" % (th, e["answer"]))
    with open(os.path.join(out, "samples.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")


# --------------------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--workdir", required=True)
        p.add_argument("--name", default="self1", help="selfgen/<name> holds the questions and answers")
        return p

    p = common(sub.add_parser("select"))
    p.add_argument("--source", default="v1.2", help="physdata build to take the questions from")
    p.add_argument("--n", type=int, default=9000)
    p.add_argument("--math-share", type=float, default=0.15)
    p.add_argument("--gen-prompt", choices=["plain", "same"], default="plain",
                   help="plain: generate physics answers with the bare question + simple instruction")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_select)

    p = common(sub.add_parser("generate"))
    p.add_argument("--shard", type=int, required=True)
    p.add_argument("--num-shards", type=int, default=3)
    p.add_argument("--backend", choices=["vllm", "hf", "mock"], default="vllm")
    p.add_argument("--model", default=MODEL_ID)
    p.add_argument("--samples", type=int, default=2, help="answers per question")
    p.add_argument("--temperature", type=float, default=0.6)
    p.add_argument("--top-p", type=float, default=0.95)
    p.add_argument("--top-k", type=int, default=50)
    p.add_argument("--repetition-penalty", type=float, default=1.0)
    p.add_argument("--max-new-tokens", type=int, default=3584)
    p.add_argument("--batch-size", type=int, default=64, help="hf backend: rows per generate call")
    p.add_argument("--chunk", type=int, default=512, help="vllm backend: answers per call (saved after each)")
    p.add_argument("--max-model-len", type=int, default=5120)
    p.add_argument("--gpu-memory-utilization", type=float, default=0.88)
    p.add_argument("--limit", type=int, default=0, help="stop after this many answers (speed test)")
    p.add_argument("--time-budget-min", type=float, default=0)
    p.set_defaults(fn=cmd_generate)

    p = common(sub.add_parser("status"))
    p.set_defaults(fn=cmd_status)

    p = common(sub.add_parser("build"))
    p.add_argument("--out", default="self1", help="train_data/<out>")
    p.add_argument("--max-new-tokens", type=int, default=3584, help="longest answer kept")
    p.add_argument("--max-answer-chars", type=int, default=4000)
    p.add_argument("--max-format-talk", type=int, default=8, help="drop answers whose thinking discusses the answer format this often")
    p.add_argument("--add-from", help="also take finished examples from train_data/<name> (e.g. self1)")
    p.add_argument("--add-styles", default="math", help="styles to take with --add-from")
    p.add_argument("--n-val", type=int, default=200)
    p.add_argument("--workers", type=int, default=2)
    p.set_defaults(fn=cmd_build)

    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
