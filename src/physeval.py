#!/usr/bin/env python3
"""
physeval.py - baseline physics evaluation harness for small LLMs (free Colab T4).

Benchmarks
  ugphysics    UGPhysics, English split (5,520 problems, 13 subjects). Prompt and
               rule-based grader are the OFFICIAL ones, imported from the UGPhysics repo.
  physicseval  PhysicsEval test split (1,962 problems). Free-text answers, so it can
               only be scored by an LLM judge using the official 7-part rubric.
  math500      MATH-500. Regression check ("did fine-tuning break maths?").

Stages (each one is resumable and writes to <workdir>)
  selftest   check the grading stack works on this machine
  prepare    download data, freeze the item list and the exact prompts
  generate   run one model configuration on the frozen items (GPU)
  grade      rule-based grading (free, deterministic, no API key)
  judge      optional LLM judge (UGPhysics MARJ second stage + PhysicsEval rubric)
  report     metrics, breakdowns, confidence intervals, head-to-head tests

Decoding is identical for every run and follows the official UGPhysics script: greedy, 4096 new
tokens, no repetition penalty. The only addition is a loop detector that stops an answer once it is
repeating itself verbatim, to save GPU time; such answers are reported as "stuck in a loop".
"""
import argparse
import ast
import collections
import csv
import datetime
import hashlib
import json
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import time
import types
import warnings

VERSION = "1.4"

# --------------------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------------------

RUNS = {
    "lfm25-1.2b-thinking": {"model": "LiquidAI/LFM2.5-1.2B-Thinking", "template_kwargs": {}},
    "qwen35-2b-nothink": {"model": "Qwen/Qwen3.5-2B", "template_kwargs": {"enable_thinking": False}},
    "qwen35-2b-think": {"model": "Qwen/Qwen3.5-2B", "template_kwargs": {"enable_thinking": True}},
}

BENCHES = ["ugphysics", "physicseval", "math500"]

UG_REPO = "https://github.com/YangLabHKUST/UGPhysics.git"
UG_REPO_SHA = "4c1a9c6a6a8e88fd80b31fbe7c8649ff271490f3"
UG_DATASET = "UGPhysics/ugphysics"
UG_SUBJECTS = [
    "AtomicPhysics", "ClassicalElectromagnetism", "ClassicalMechanics", "Electrodynamics",
    "GeometricalOptics", "QuantumMechanics", "Relativity", "SemiconductorPhysics",
    "Solid-StatePhysics", "StatisticalMechanics", "TheoreticalMechanics", "Thermodynamics",
    "WaveOptics",
]
# System prompt used by the official UGPhysics script for open models.
UG_SYSTEM = "Please reason step by step, and put your final answer within \\boxed{}."
UG_PRECISION = 1e-2  # default of the official eval.py

PE_REPO = "https://github.com/areebuzair/PhysicsEval.git"
PE_REPO_SHA = "488e6ed8f5a23204bea5b8f3cecc48b0dd4af367"
PE_TEST_FILE = os.path.join("BASE SOLUTION", "test.json")
PE_EVAL_FILE = os.path.join("EVALUATIONS", "eval_ollama.py")
PE_DIMS5 = ["mathematical_accuracy", "logical_consistency", "completeness",
            "clarity_and_coherence", "formulas_principles", "assumptions_made"]
PE_OVERALL = "overall_correctness"

MATH500_DATASET = "HuggingFaceH4/MATH-500"
MATH_SUFFIX = "\n\nPlease reason step by step, and put your final answer within \\boxed{}."

SEED = 20261006
WAVE = 25  # generation proceeds in waves of 25 items per group, so partial runs stay balanced
# Official UGPhysics decoding: greedy, 4096 new tokens, no repetition penalty.
GEN_DEFAULTS = {"max_new_tokens": 4096, "repetition_penalty": 1.0, "temperature": 0.0, "loop_stop": True}


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------

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


def sha1(s):
    return hashlib.sha1(s.encode("utf-8", "replace")).hexdigest()


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def read_jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # a half-written last line after a crash is simply ignored
    return rows


def append_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def write_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _clean(o):
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [_clean(v) for v in o]
    return o


def write_json(path, obj):
    obj = _clean(obj)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def P(workdir, *parts):
    return os.path.join(workdir, *parts)


def run_dir(workdir, run):
    return P(workdir, "runs", run)


def parse_per_group(text):
    """'ugphysics=100,physicseval=25,math500=30' -> dict. 0 means every item.
    A range 'ugphysics=100:200' takes only the items ranked 100 to 199 in each group: ranks below 100 are the
    development slice (used while choosing models), so a range starting at 100 is a held-out final test."""
    out = {}
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        k, v = part.split("=")
        if k.strip() not in BENCHES:
            raise SystemExit("unknown benchmark in --per-group: %r" % k)
        v = v.strip()
        if ":" in v:
            lo, hi = (int(x) for x in v.split(":"))
            if not 0 <= lo < hi:
                raise SystemExit("bad range in --per-group: %r (use FROM:TO with FROM < TO)" % part)
            out[k.strip()] = [lo, hi]
        else:
            out[k.strip()] = int(v)
    return out


# --------------------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------------------

def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def mcnemar_exact(b, c):
    """Two-sided exact McNemar test on the discordant pairs (b: only A right, c: only B right)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2.0 ** n
    return min(1.0, 2 * tail)


def weighted_mean(values_by_stratum, weights):
    tot = sum(weights[s] for s in values_by_stratum if values_by_stratum[s])
    if tot == 0:
        return float("nan")
    return sum(weights[s] * (sum(v) / len(v)) for s, v in values_by_stratum.items() if v) / tot


def stratified_bootstrap(values_by_stratum, weights, n_boot=2000, seed=SEED):
    """95% CI of the stratum-weighted mean; resamples inside each stratum."""
    import numpy as np
    rng = np.random.default_rng(seed)
    strata = [s for s, v in values_by_stratum.items() if v]
    tot = sum(weights[s] for s in strata)
    if not strata or tot == 0:
        return (float("nan"), float("nan"))
    acc = np.zeros(n_boot)
    for s in strata:
        x = np.asarray(values_by_stratum[s], dtype=float)
        idx = rng.integers(0, len(x), size=(n_boot, len(x)))
        acc += (weights[s] / tot) * x[idx].mean(axis=1)
    return (float(np.percentile(acc, 2.5)), float(np.percentile(acc, 97.5)))


def quantile(xs, q):
    if not xs:
        return float("nan")
    xs = sorted(xs)
    i = (len(xs) - 1) * q
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


# --------------------------------------------------------------------------------------
# Official benchmark code (cloned, never copied)
# --------------------------------------------------------------------------------------

def git_clone(url, dest, sha):
    if not os.path.isdir(os.path.join(dest, ".git")):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        log("cloning", url)
        subprocess.run(["git", "clone", "--quiet", url, dest], check=True)
    r = subprocess.run(["git", "-C", dest, "checkout", "--quiet", sha], capture_output=True, text=True)
    if r.returncode != 0:
        subprocess.run(["git", "-C", dest, "fetch", "--quiet", "--all"], capture_output=True)
        r = subprocess.run(["git", "-C", dest, "checkout", "--quiet", sha], capture_output=True, text=True)
    if r.returncode != 0:
        log("WARNING: could not check out pinned commit %s of %s; using the default branch." % (sha[:8], url))
    head = subprocess.run(["git", "-C", dest, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    return head


def cache_root():
    """Downloads live on the local disk, not on Drive (Drive has no symlinks and is slow for git).
    They are re-fetched in a new session; pinned commits keep them identical."""
    return os.environ.get("PHYSEVAL_CACHE") or os.path.join(tempfile.gettempdir(), "physeval_cache")


def ug_repo_dir(workdir=None):
    return os.path.join(cache_root(), "UGPhysics")


def pe_repo_dir(workdir=None):
    return os.path.join(cache_root(), "PhysicsEval")


def hf_cache():
    return os.path.join(cache_root(), "hf")


def ensure_repos():
    return (git_clone(UG_REPO, ug_repo_dir(), UG_REPO_SHA), git_clone(PE_REPO, pe_repo_dir(), PE_REPO_SHA))


def import_ug(workdir, need_judge=True):
    """Import the official UGPhysics modules. Returns (utils_module, Judger_class_or_None)."""
    codes = os.path.join(ug_repo_dir(workdir), "codes")
    if not os.path.isdir(codes):
        git_clone(UG_REPO, ug_repo_dir(), UG_REPO_SHA)
    if codes not in sys.path:
        sys.path.insert(0, codes)
    warnings.filterwarnings("ignore", category=SyntaxWarning)
    # judge.py imports openai/httpx at module level only for its API judge, which we replace.
    for name in ("openai", "httpx", "chardet"):
        try:
            __import__(name)
        except Exception:
            stub = types.ModuleType(name)
            stub.OpenAI = object
            stub.RateLimitError = Exception
            sys.modules[name] = stub
    import utils as ug_utils  # noqa
    if not hasattr(ug_utils, "make_prompt"):
        raise SystemExit("A different module named 'utils' shadowed the UGPhysics one.")
    if not need_judge:
        return ug_utils, None
    from judge import Judger  # noqa
    return ug_utils, Judger


def pe_rubric_prompt_fn(workdir):
    """Load create_evaluation_prompt() from the official PhysicsEval script without running the script."""
    path = os.path.join(pe_repo_dir(workdir), PE_EVAL_FILE)
    with open(path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "create_evaluation_prompt":
            ns = {}
            exec(compile(ast.Module(body=[node], type_ignores=[]), path, "exec"), ns)
            return ns["create_evaluation_prompt"]
    raise SystemExit("create_evaluation_prompt not found in " + path)


# --------------------------------------------------------------------------------------
# prepare: data -> frozen manifest
# --------------------------------------------------------------------------------------

def load_ugphysics_rows(workdir, local_dir=None):
    rows, rev = {}, None
    for sub in UG_SUBJECTS:
        path = None
        if local_dir:
            path = os.path.join(local_dir, sub, "en.jsonl")
        else:
            from huggingface_hub import hf_hub_download
            try:
                path = hf_hub_download(UG_DATASET, "%s/en.jsonl" % sub, repo_type="dataset",
                                       cache_dir=hf_cache())
            except Exception as e:  # layout changed: fall back to the datasets loader
                log("  direct download failed for %s (%s); trying datasets.load_dataset" % (sub, type(e).__name__))
                from datasets import load_dataset
                ds = load_dataset(UG_DATASET, sub, split="en", cache_dir=hf_cache())
                rows[sub] = [dict(r) for r in ds]
                continue
        rows[sub] = read_jsonl(path)
        if not rows[sub]:
            raise SystemExit("no rows read from " + str(path))
    if not local_dir:
        try:
            from huggingface_hub import HfApi
            rev = HfApi().dataset_info(UG_DATASET).sha
        except Exception:
            rev = None
    return rows, rev


def build_ugphysics(workdir, local_dir=None):
    ug_utils, _ = import_ug(workdir, need_judge=False)
    rows, rev = load_ugphysics_rows(workdir, local_dir)
    items = []
    for sub in UG_SUBJECTS:
        for i, r in enumerate(rows[sub]):
            if str(r.get("language", "EN")).upper() != "EN":
                continue
            try:
                head = ug_utils.make_prompt(r)
            except SystemExit:
                raise SystemExit("official make_prompt rejected row %d of %s (answer_type=%r)"
                                 % (i, sub, r.get("answer_type")))
            items.append({
                "uid": "ugphysics/%s/%d" % (sub, i), "bench": "ugphysics", "stratum": sub,
                "messages": [{"role": "system", "content": UG_SYSTEM},
                             {"role": "user", "content": head + "\n\n" + r["problem"]}],
                "problem": r["problem"], "solution": r.get("solution", ""), "gold": r["answers"],
                "answer_type": r.get("answer_type", ""), "is_multiple_answer": bool(r.get("is_multiple_answer")),
                "unit": r.get("unit"), "domain": r.get("domain", ""), "subject": r.get("subject", sub),
                "topic": r.get("topic", ""), "level": r.get("level") or "Unlabelled", "src_index": r.get("index"),
            })
    return items, {"dataset": UG_DATASET, "revision": rev, "split": "en"}


def build_physicseval(workdir, local_file=None):
    path = local_file or os.path.join(pe_repo_dir(workdir), PE_TEST_FILE)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    items = []
    for r in data:
        prob = r["problem"]
        # Verbatim prompt of the official PROPOSER.py (single user turn, no system prompt).
        content = ("You are an expert on Physics. You solve problems step by step while maintaining logical "
                   "consistency. Solve the following Physics problem: %s"
                   "Finally, write the final answers in brief. Make sure you write all equations in LaTeX." % prob)
        d = r.get("problem_difficulty")
        items.append({
            "uid": "physicseval/%s" % r["Problem_ID"], "bench": "physicseval", "stratum": r.get("category", "?"),
            "messages": [{"role": "user", "content": content}],
            "problem": prob, "solution": r.get("elaborated_solution_steps", ""),
            "gold": r.get("final_answers_in_brief", []), "category": r.get("category", "?"),
            "difficulty": d, "problem_id": r["Problem_ID"],
            "difficulty_band": ("1-4" if d <= 4 else "5-6" if d <= 6 else "7-10") if isinstance(d, (int, float)) else "?",
        })
    return items, {"repo": PE_REPO, "file": PE_TEST_FILE}


def build_math500(workdir, local_file=None):
    if local_file:
        data = read_jsonl(local_file)
        rev = None
    else:
        from datasets import load_dataset
        data = [dict(r) for r in load_dataset(MATH500_DATASET, split="test", cache_dir=hf_cache())]
        try:
            from huggingface_hub import HfApi
            rev = HfApi().dataset_info(MATH500_DATASET).sha
        except Exception:
            rev = None
    items = []
    for i, r in enumerate(data):
        items.append({
            "uid": "math500/%s" % r.get("unique_id", i), "bench": "math500", "stratum": r.get("subject", "?"),
            "messages": [{"role": "user", "content": r["problem"] + MATH_SUFFIX}],
            "problem": r["problem"], "solution": r.get("solution", ""), "gold": "\\boxed{%s}" % r["answer"],
            "subject": r.get("subject", "?"), "level": "Level %s" % r.get("level", "?"),
        })
    return items, {"dataset": MATH500_DATASET, "revision": rev, "split": "test"}


def assign_ranks(items):
    by = collections.defaultdict(list)
    for it in items:
        by[it["stratum"]].append(it)
    for s, lst in by.items():
        lst.sort(key=lambda it: sha1("%d:%s" % (SEED, it["uid"])))
        for k, it in enumerate(lst):
            it["rank"] = k
    return {s: len(lst) for s, lst in by.items()}


def cmd_prepare(a):
    wd = a.workdir
    meta = read_json(P(wd, "data", "manifest_meta.json"), {}) or {}
    benches = [b.strip() for b in a.benchmarks.split(",") if b.strip()]
    ug_head, pe_head = ensure_repos()
    for b in benches:
        out = P(wd, "data", "items_%s.jsonl" % b)
        if os.path.exists(out) and not a.force:
            log("%-12s already prepared (%d items). Use --force to rebuild." % (b, len(read_jsonl(out))))
            continue
        log("preparing", b, "...")
        if b == "ugphysics":
            items, src = build_ugphysics(wd, a.ugphysics_dir)
            src["code_commit"] = ug_head
        elif b == "physicseval":
            items, src = build_physicseval(wd, a.physicseval_file)
            src["code_commit"] = pe_head
        elif b == "math500":
            items, src = build_math500(wd, a.math500_file)
        else:
            raise SystemExit("unknown benchmark " + b)
        sizes = assign_ranks(items)
        write_jsonl(out, items)
        meta[b] = {"n": len(items), "strata": sizes, "source": src, "seed": SEED, "prepared": now()}
        log("  %d items in %d groups -> %s" % (len(items), len(sizes), out))
    write_json(P(wd, "data", "manifest_meta.json"), meta)
    log("\nItems per benchmark")
    for b in BENCHES:
        if b in meta:
            log("  %-12s %5d items, %2d groups" % (b, meta[b]["n"], len(meta[b]["strata"])))


def load_items(workdir, bench):
    path = P(workdir, "data", "items_%s.jsonl" % bench)
    items = read_jsonl(path)
    if not items:
        raise SystemExit("%s not prepared. Run the prepare step first." % bench)
    return items


def planned(items, per_group):
    if isinstance(per_group, (list, tuple)):  # a rank range [from, to)
        lo, hi = per_group
        return [it for it in items if lo <= it["rank"] < hi]
    return [it for it in items if not per_group or it["rank"] < per_group]


# --------------------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------------------

def split_thinking(text, prompt_opens_think):
    """-> (thinking, final_answer, thinking_closed)."""
    if "</think>" in text:
        think, ans = text.rsplit("</think>", 1)
        return think.replace("<think>", "").strip(), ans.strip(), True
    if prompt_opens_think or "<think>" in text:
        return text.replace("<think>", "").strip(), "", False
    return "", text.strip(), True


def detect_loop(tail, min_span=120, max_period=60, min_repeats=4):
    """True if the sequence ends in an exact periodic repetition covering >= min_span tokens."""
    n = len(tail)
    for p in range(1, max_period + 1):
        span = p * max(min_repeats, -(-min_span // p))
        if span > n:
            continue
        ok = True
        for i in range(n - span + p, n):
            if tail[i] != tail[i - p]:
                ok = False
                break
        if ok:
            return True
    return False


def plan_batches(order, lengths, batch_size, exact):
    """order: item indices in processing order. exact=True only groups prompts of equal token length."""
    batches, cur = [], []
    for i in order:
        if cur and (len(cur) >= batch_size or (exact and lengths[i] != lengths[cur[0]])):
            batches.append(cur)
            cur = []
        cur.append(i)
    if cur:
        batches.append(cur)
    return batches


def resolve_run(a):
    base = max((k for k in RUNS if a.run == k or a.run.startswith(k + "-")), key=len, default=None)
    cfg = dict(RUNS.get(base, {}))  # "qwen35-2b-think-rp105" inherits the settings of "qwen35-2b-think"
    if a.model:
        cfg["model"] = a.model
    if "model" not in cfg:
        raise SystemExit("run %r is not predefined, so --model is required. Predefined: %s" % (a.run, ", ".join(RUNS)))
    tk = dict(cfg.get("template_kwargs", {}))
    if a.enable_thinking is not None:
        tk["enable_thinking"] = a.enable_thinking.lower() in ("1", "true", "yes")
    cfg["template_kwargs"] = tk
    cfg["adapter"] = a.adapter
    cfg["max_new_tokens"] = a.max_new_tokens
    cfg["repetition_penalty"] = a.repetition_penalty
    cfg["temperature"] = a.temperature
    cfg["loop_stop"] = not a.no_loop_stop
    cfg["dtype"] = a.dtype
    return cfg


def cfg_hash(cfg):
    keys = ["model", "adapter", "template_kwargs", "max_new_tokens", "repetition_penalty", "temperature", "loop_stop"]
    return sha1(json.dumps({k: cfg.get(k) for k in keys}, sort_keys=True))[:12]


class HFBackend:
    def __init__(self, cfg):
        import torch
        import transformers
        from transformers import AutoTokenizer
        self.torch, self.cfg = torch, cfg
        if not torch.cuda.is_available():
            raise SystemExit("No GPU. In Colab: Runtime > Change runtime type > T4 GPU.")
        name = cfg.get("dtype") or "auto"
        if name == "auto":
            name = "bfloat16" if torch.cuda.get_device_capability(0)[0] >= 8 else "float16"
        dtype = getattr(torch, name)
        mid = cfg["model"]
        log("loading tokenizer:", mid)
        self.tok = AutoTokenizer.from_pretrained(mid)
        self.tok.padding_side = "left"
        if self.tok.pad_token_id is None:
            self.tok.pad_token = self.tok.eos_token
        errors, model = [], None
        for cls_name in ("AutoModelForCausalLM", "AutoModelForImageTextToText", "AutoModelForMultimodalLM"):
            cls = getattr(transformers, cls_name, None)
            if cls is None:
                continue
            for kw in ("dtype", "torch_dtype"):
                try:
                    model = cls.from_pretrained(mid, **{kw: dtype})
                    break
                except TypeError as e:  # this transformers version uses the other keyword
                    errors.append("%s(%s): %s" % (cls_name, kw, str(e)[:120]))
                except Exception as e:
                    errors.append("%s: %s: %s" % (cls_name, type(e).__name__, str(e)[:160]))
                    break
            if model is not None:
                log("loaded with", cls_name, "dtype", name)
                break
        if model is None:
            raise SystemExit("Could not load %s:\n  %s\nTry: pip install -U transformers "
                             "(or the git main version) and restart the runtime." % (mid, "\n  ".join(errors)))
        model = model.to("cuda")
        if cfg.get("adapter"):  # merged on the GPU: DoRA needs weight norms, and fp16 norms may fail on CPU
            import_peft()
            from peft import PeftModel
            log("merging adapter:", cfg["adapter"])
            model = PeftModel.from_pretrained(model, cfg["adapter"]).merge_and_unload()
        self.model = model.eval()
        actual = next(self.model.parameters()).dtype
        if actual != dtype:
            log("model loaded as %s; converting to %s" % (actual, name))
            self.model = self.model.to(dtype)
        torch.manual_seed(SEED)
        eos = set()
        g = getattr(self.model.generation_config, "eos_token_id", None)
        if isinstance(g, int):
            eos.add(g)
        elif g:
            eos.update(int(x) for x in g)
        if self.tok.eos_token_id is not None:
            eos.add(int(self.tok.eos_token_id))
        tid = self.tok.convert_tokens_to_ids("<|im_end|>")
        if isinstance(tid, int) and tid >= 0 and tid != self.tok.unk_token_id:
            eos.add(tid)
        self.eos = sorted(eos)
        keep = {"<think>", "</think>"}
        self.strip_tokens = [t for t in set(self.tok.all_special_tokens) if t and t not in keep]
        self.info = {
            "dtype": name, "gpu": torch.cuda.get_device_name(0), "torch": torch.__version__,
            "transformers": transformers.__version__, "model_class": type(self.model).__name__,
            "model_commit": getattr(self.model.config, "_commit_hash", None), "eos_ids": self.eos,
            "n_params": int(sum(p.numel() for p in self.model.parameters())),
        }

    def render(self, messages):
        return self.tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                            **self.cfg.get("template_kwargs", {}))

    def encode_len(self, text):
        return len(self.tok(text, add_special_tokens=False)["input_ids"])

    def count(self, text):
        return self.encode_len(text) if text else 0

    def generate(self, texts, max_new_tokens=None, loop_stop=None):
        torch = self.torch
        cfg = self.cfg
        max_new = max_new_tokens or cfg["max_new_tokens"]
        enc = self.tok(texts, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
        in_len = enc["input_ids"].shape[1]
        kw = dict(max_new_tokens=max_new, pad_token_id=self.tok.pad_token_id, eos_token_id=self.eos)
        if cfg.get("temperature", 0) and cfg["temperature"] > 0:
            kw.update(do_sample=True, temperature=cfg["temperature"])
            if cfg.get("top_p"):
                kw["top_p"] = cfg["top_p"]
            if cfg.get("top_k"):
                kw["top_k"] = cfg["top_k"]
        else:
            kw.update(do_sample=False)
        if cfg.get("repetition_penalty") and cfg["repetition_penalty"] != 1.0:
            kw["repetition_penalty"] = cfg["repetition_penalty"]
        stopper = None
        use_stop = cfg.get("loop_stop", True) if loop_stop is None else loop_stop
        if use_stop:
            from transformers import StoppingCriteria, StoppingCriteriaList
            ignore = set(self.eos) | {self.tok.pad_token_id}

            class LoopStop(StoppingCriteria):
                def __init__(self):
                    self.stopped = {}

                def __call__(self, input_ids, scores, **kwargs):
                    n_gen = input_ids.shape[1] - in_len
                    done = torch.zeros(input_ids.shape[0], dtype=torch.bool, device=input_ids.device)
                    for r in self.stopped:
                        done[r] = True
                    if n_gen < 120 or n_gen % 32 != 0:
                        return done
                    tails = input_ids[:, -min(n_gen, 512):].tolist()
                    for r, tail in enumerate(tails):
                        if r in self.stopped or tail[-1] in ignore:
                            continue
                        if detect_loop(tail):
                            self.stopped[r] = n_gen
                            done[r] = True
                    return done

            stopper = LoopStop()
            kw["stopping_criteria"] = StoppingCriteriaList([stopper])
        with torch.inference_mode():
            out = self.model.generate(input_ids=enc["input_ids"], attention_mask=enc["attention_mask"], **kw)
        res = []
        eos = set(self.eos)
        for r in range(out.shape[0]):
            seq = out[r, in_len:].tolist()
            reason, n = "length", len(seq)
            if stopper is not None and r in stopper.stopped:
                reason, n = "loop", min(stopper.stopped[r], len(seq))
            else:
                for k, t in enumerate(seq):
                    if t in eos:
                        reason, n = "stop", k
                        break
                else:
                    while n > 0 and seq[n - 1] == self.tok.pad_token_id:
                        n -= 1
            text = self.tok.decode(seq[:n], skip_special_tokens=False)
            for t in self.strip_tokens:
                text = text.replace(t, "")
            res.append({"text": text, "ids": seq[:n], "n_new_tokens": n, "finish_reason": reason,
                        "n_prompt_tokens": int(enc["attention_mask"][r].sum().item())})
        del out, enc
        return res

    def is_oom(self, e):
        return isinstance(e, self.torch.cuda.OutOfMemoryError) or "out of memory" in str(e).lower()

    def free(self):
        import gc
        gc.collect()
        self.torch.cuda.empty_cache()


class MockBackend:
    """No GPU, no model: fabricates answers so the whole pipeline can be dry-run. Never use for results."""

    def __init__(self, cfg, items_by_prompt):
        self.cfg, self.lookup = cfg, items_by_prompt
        self.skill = {"lfm25-1.2b-thinking": 0.42, "qwen35-2b-nothink": 0.30, "qwen35-2b-think": 0.38}
        self.info = {"dtype": "none", "gpu": "mock", "torch": "-", "transformers": "-", "model_class": "Mock",
                     "model_commit": None, "eos_ids": [], "n_params": 0}
        self.opens = bool(cfg.get("template_kwargs", {}).get("enable_thinking"))
        self.thinks = self.opens or "thinking" in cfg["model"].lower()

    def render(self, messages):
        return "\n".join("<|im_start|>%s\n%s<|im_end|>" % (m["role"], m["content"]) for m in messages) + \
            "\n<|im_start|>assistant\n" + ("<think>\n" if self.opens else "")

    def encode_len(self, text):
        return max(1, len(text) // 4)

    count = encode_len

    def generate(self, texts, max_new_tokens=None, loop_stop=None):
        res = []
        for t in texts:
            it = self.lookup[t]
            rnd = random.Random(sha1(self.cfg["_run"] + it["uid"]))
            p = self.skill.get(self.cfg["_run"], 0.35)
            u = rnd.random()
            gold = it["gold"] if isinstance(it["gold"], str) else "; ".join(map(str, it["gold"]))
            think = ("<think>" if not self.opens else "") + "Let me set up the physical model. " * rnd.randint(3, 40)
            reason = "stop"
            if u < 0.04 and self.thinks:
                text, reason = think, "length"          # ran out of budget while thinking
            elif u < 0.07:
                text, reason = (think + "</think>" if self.thinks else "") + "x = 1 " * 200, "loop"
            else:
                right = rnd.random() < p
                if it["bench"] == "physicseval":
                    body = "Step 1 ... Step 2 ... Final answers: " + (gold if right else "42")
                elif right:
                    inner = gold
                    if rnd.random() < 0.25 and it.get("answer_type") == "NV" and it.get("unit"):
                        inner = gold[:-1] + " \\text{ eV}}"
                    body = "So the final answer is %s." % inner
                elif rnd.random() < 0.2:
                    body = "The result follows from the equations above."
                else:
                    body = "So the final answer is \\boxed{%d}." % rnd.randint(2, 97)
                text = (think + "</think>\n\n" if self.thinks else "") + body
            n = max(1, len(text) // 4)
            res.append({"text": text, "ids": [], "n_new_tokens": n, "finish_reason": reason,
                        "n_prompt_tokens": max(1, len(t) // 4)})
        return res

    def is_oom(self, e):
        return False

    def free(self):
        pass


def padding_check(backend, texts, lengths, n_tokens=48):
    """Greedy decode a few prompts alone and as one padded batch. If they disagree, padding is unsafe."""
    order = sorted(range(len(texts)), key=lambda i: lengths[i])
    pick = sorted({order[0], order[len(order) // 3], order[2 * len(order) // 3], order[-1]})
    if len(pick) < 2:
        return {"safe": True, "note": "not enough prompts to test"}
    sample = [texts[i] for i in pick]
    single = [backend.generate([t], max_new_tokens=n_tokens, loop_stop=False)[0]["ids"] for t in sample]
    batch = [r["ids"] for r in backend.generate(sample, max_new_tokens=n_tokens, loop_stop=False)]
    fr = []
    for s, b in zip(single, batch):
        k = 0
        while k < min(len(s), len(b)) and s[k] == b[k]:
            k += 1
        fr.append(1.0 if max(len(s), len(b)) == 0 else k / max(len(s), len(b)))
    safe = (sum(fr) / len(fr) >= 0.75) and (min(fr) >= 0.5)
    return {"safe": bool(safe), "agreement": [round(x, 3) for x in fr],
            "prompt_tokens": [lengths[i] for i in pick]}


def cmd_generate(a):
    wd = a.workdir
    cfg = resolve_run(a)
    cfg["_run"] = a.run
    rd = run_dir(wd, a.run)
    meta_path = P(rd, "meta.json")
    meta = read_json(meta_path, {}) or {}
    h = cfg_hash(cfg)
    if meta.get("cfg_hash") and meta["cfg_hash"] != h and not a.smoke:
        raise SystemExit("Run %r already exists with different settings.\n  saved: %s\n  now:   %s\n"
                         "Use a new --run name for a new configuration."
                         % (a.run, json.dumps(meta.get("cfg"), sort_keys=True),
                            json.dumps({k: v for k, v in cfg.items() if k != "_run"}, sort_keys=True)))
    benches = [b.strip() for b in a.benchmarks.split(",") if b.strip()]
    per_group = parse_per_group(a.per_group)
    for b in benches:  # a run covers one slice: never mix the development slice and a held-out range
        new, old = per_group.get(b, 0), (meta.get("plan") or {}).get(b)
        if old is not None and (isinstance(new, list) or isinstance(old, list)) and new != old:
            raise SystemExit("Run %r already covers %s items %s; this asks for %s.\n"
                             "Use a new --run name for a different slice (e.g. add -test)." % (a.run, b, old, new))
    todo_all = {}
    for b in benches:
        items = planned(load_items(wd, b), per_group.get(b, 0))
        done = {r["uid"] for r in read_jsonl(P(rd, "gen_%s.jsonl" % b)) if r.get("cfg_hash") == h}
        todo = [it for it in items if it["uid"] not in done]
        if a.smoke:
            todo = sorted(todo, key=lambda it: (it["rank"], it["stratum"]))[:a.max_items or 8]
        elif a.max_items:
            todo = todo[:a.max_items]
        todo_all[b] = (items, todo, len(done))
        log("%-12s planned %5d | done %5d | to do %5d" % (b, len(items), len(done), len(todo)))
    if not any(t[1] for t in todo_all.values()):
        log("Nothing left to generate for run %r." % a.run)
        return
    if a.backend == "mock":
        lookup = {}
        backend = MockBackend(cfg, lookup)
        for b, (_, todo, _) in todo_all.items():
            for it in todo:
                lookup[backend.render(it["messages"])] = it
    else:
        backend = HFBackend(cfg)
    if not a.smoke:
        meta.update({"run": a.run, "cfg": {k: v for k, v in cfg.items() if k != "_run"}, "cfg_hash": h,
                     "backend": a.backend, "info": backend.info, "harness_version": VERSION,
                     "updated": now()})
        meta.setdefault("created", now())
        meta.setdefault("plan", {})
        for b in benches:
            new, old = per_group.get(b, 0), meta["plan"].get(b)
            if isinstance(new, list) or old is None:
                meta["plan"][b] = new
            else:
                meta["plan"][b] = 0 if (old == 0 or new == 0) else max(old, new)
        write_json(meta_path, meta)

    grand_tokens, grand_secs = 0, 0.0
    bs = a.batch_size  # a batch size learned after an out-of-memory error is kept for the rest of the session
    for b in benches:
        items, todo, _ = todo_all[b]
        if not todo:
            continue
        texts = [backend.render(it["messages"]) for it in todo]
        lengths = [backend.encode_len(t) for t in texts]
        opens = [t.rstrip().endswith("<think>") for t in texts]
        batching = a.batching
        if batching == "auto":
            if "padding" not in meta and a.backend != "mock" and len(texts) >= 4:
                log("checking that padded batches reproduce single-prompt outputs ...")
                meta["padding"] = padding_check(backend, texts, lengths)
                log("  ", json.dumps(meta["padding"]))
                if not a.smoke:
                    write_json(meta_path, meta)
            batching = "padded" if meta.get("padding", {"safe": True}).get("safe", True) else "exact"
            if batching == "exact":
                log("  padding changes this model's outputs -> batching only prompts of equal length")
        order = sorted(range(len(todo)), key=lambda i: (todo[i]["rank"] // WAVE, -lengths[i]))
        if a.smoke:
            log("\n===== rendered prompt of the first %s item =====\n%s\n===== end of prompt =====" % (b, texts[order[0]]))
        out_path = P(rd, ("smoke_%s.jsonl" if a.smoke else "gen_%s.jsonl") % b)
        if a.smoke and os.path.exists(out_path):
            os.remove(out_path)
        queue = collections.deque(plan_batches(order, lengths, bs, batching == "exact"))
        n_done, n_tok, secs, t_start = 0, 0, 0.0, time.time()
        reasons = collections.Counter()
        while queue:
            batch = queue.popleft()
            t0 = time.time()
            try:
                res = backend.generate([texts[i] for i in batch])
            except Exception as e:
                if not backend.is_oom(e):
                    raise
                backend.free()
                if len(batch) == 1:
                    log("  out of memory on a single item (%s); recorded as failed" % todo[batch[0]]["uid"])
                    res = [{"text": "", "ids": [], "n_new_tokens": 0, "finish_reason": "oom",
                            "n_prompt_tokens": lengths[batch[0]]}]
                else:
                    bs = max(1, len(batch) // 2)
                    log("  out of memory: batch size is now %d" % bs)
                    rest = [i for bt in queue for i in bt]
                    queue = collections.deque(plan_batches(batch + rest, lengths, bs, batching == "exact"))
                    continue
            dt = time.time() - t0
            rows = []
            for i, r in zip(batch, res):
                think, ans, closed = split_thinking(r["text"], opens[i])
                rows.append({
                    "uid": todo[i]["uid"], "bench": b, "run": a.run, "cfg_hash": h, "completion": r["text"],
                    "prompt_opens_think": opens[i], "n_prompt_tokens": r["n_prompt_tokens"],
                    "n_new_tokens": r["n_new_tokens"], "n_think_tokens": backend.count(think),
                    "finish_reason": r["finish_reason"], "batch_size": len(batch),
                    "batch_seconds": round(dt, 2), "prompt_sha": sha1(texts[i])[:12], "ts": now(),
                })
                reasons[r["finish_reason"]] += 1
                n_tok += r["n_new_tokens"]
            append_jsonl(out_path, rows)
            n_done += len(batch)
            secs += dt
            rate = n_tok / max(secs, 1e-9)
            eta = (len(todo) - n_done) * (n_tok / max(n_done, 1)) / max(rate, 1e-9)
            log("[%s] %s %d/%d | batch %d in %.0fs | %.0f tok/s | avg %.0f new tok/item | ETA %.1f h | %s"
                % (now()[11:], b, n_done, len(todo), len(batch), dt, rate, n_tok / max(n_done, 1), eta / 3600,
                   dict(reasons)))
            if a.smoke and n_done <= len(batch):
                log("\n===== first completion (%s) =====\n%s\n===== end =====" % (rows[0]["finish_reason"], rows[0]["completion"][:6000]))
            if a.time_budget_min and (time.time() - t_start) / 60 > a.time_budget_min:
                log("time budget reached; stopping cleanly (rerun the same cell to continue)")
                queue.clear()
        grand_tokens += n_tok
        grand_secs += secs
        if a.smoke and n_done:
            full = len(planned(items, per_group.get(b, 0)))
            rate, avg = n_tok / max(secs, 1e-9), n_tok / n_done
            log("\nSMOKE %s: %.0f tok/s, %.0f new tokens per item, finish reasons %s" % (b, rate, avg, dict(reasons)))
            log("  estimate for the %d planned %s items: %.1f GPU-hours (rough; small sample)"
                % (full, b, full * avg / max(rate, 1e-9) / 3600))
    if not a.smoke:
        meta["gpu_seconds"] = round(meta.get("gpu_seconds", 0) + grand_secs, 1)
        meta["updated"] = now()
        write_json(meta_path, meta)
    log("\nDone: %d new tokens in %.2f GPU-hours." % (grand_tokens, grand_secs / 3600))


# --------------------------------------------------------------------------------------
# Rule-based grading
# --------------------------------------------------------------------------------------

_UNIT = (r"(?:(?:[kMGmunpfc]|\\mu|µ|μ)?(?:mol|rad|ohm|bar|atm|cal|erg|dyn|min|eV|Hz|Pa|Wb|kg|cm|fm|nm|"
         r"m|g|s|A|K|N|J|W|C|V|F|T|H|L|Å|Ω|\\Omega)|\\%|%|°\s*[CFK]?|\^\s*\{?\s*\\circ\s*\}?\s*[CFK]?)")
_EXP = r"\^\s*(?:\{\s*-?\d+\s*\}|-?\d+)"
_NUM = (r"\s*[-+]?\s*(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
        r"(?:\s*(?:\\times|\\cdot|\*)\s*10\s*\^\s*(?:\{\s*[-+]?\d+\s*\}|[-+]?\d+))?")
_WRAPPED = re.compile(r"\\(?:text|mathrm|textrm|mathit|operatorname)\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}(?:\s*" + _EXP + ")?")
_BARE_UNITS = re.compile(r"^\s*" + _UNIT + r"(?:" + _UNIT + r"|[\s/·.()]|\\cdot|" + _EXP + r")*$")


def last_boxed_span(text):
    i = text.rfind("\\boxed{")
    if i < 0:
        return None
    j, depth = i + len("\\boxed{"), 1
    while j < len(text) and depth:
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        j += 1
    return (i + len("\\boxed{"), j - 1) if depth == 0 else None


def strip_units(answer_text):
    """If the last \\boxed{} is 'number + unit', return the text with the unit removed, else None."""
    span = last_boxed_span(answer_text)
    if not span:
        return None
    inner = answer_text[span[0]:span[1]]
    m = re.match(_NUM, inner)
    if not m or not m.group(0).strip():
        return None
    rest = inner[m.end():]
    left = _WRAPPED.sub(" ", rest)
    had_wrapped = left != rest
    left = re.sub(r"\\[,;!: ]|~|\\quad|\\qquad", " ", left).strip()
    if had_wrapped:
        left = left.lstrip(" /·.").strip()
    if not left:
        if not had_wrapped:
            return None
    elif not _BARE_UNITS.match(left):
        return None
    return answer_text[:span[0]] + m.group(0).strip() + answer_text[span[1]:]


_JUDGER = None


def _judger(workdir):
    global _JUDGER
    if _JUDGER is None:
        _, Judger = import_ug(workdir)
        _JUDGER = Judger(strict_extract=True)
    return _JUDGER


def _extract_list(j, text):
    try:
        x = j.extract_ans(text)
        x = j.split_by_comma(x)
        x = j.trans_plus_minus_sign(x)
        return [j.normalize_answer(i) if isinstance(i, str) else i for i in x]
    except Exception:
        return []


def grade_task(task):
    """Runs inside a worker process. Uses the official UGPhysics rule judge."""
    j = _judger(task["workdir"])
    ans, gold, prec = task["answer"], task["gold"], task["precision"]
    out = {"rule": False, "rule_units": False, "pred": [], "gold_norm": []}
    if not ans.strip():
        return out
    out["gold_norm"] = [str(x) for x in _extract_list(j, gold)]
    out["pred"] = [str(x) for x in _extract_list(j, ans)]
    try:
        out["rule"] = bool(j.auto_judge(ans, gold, precision=prec))
    except Exception:
        out["rule"] = False
    out["rule_units"] = out["rule"]
    if not out["rule"] and task.get("try_units"):
        alt = strip_units(ans)
        if alt:
            try:
                out["rule_units"] = bool(j.auto_judge(alt, gold, precision=prec))
            except Exception:
                pass
    return out


def _worker_loop(conn):
    conn.send("ready")
    while True:
        try:
            task = conn.recv()
        except EOFError:
            return
        if task is None:
            return
        try:
            conn.send(("ok", grade_task(task)))
        except Exception as e:
            conn.send(("err", repr(e)[:200]))


class GradePool:
    """Process pool with a hard per-item timeout; a hung symbolic comparison cannot stall the run."""

    def __init__(self, n, timeout):
        import multiprocessing as mp
        try:
            self.ctx = mp.get_context("fork")
        except ValueError:
            self.ctx = mp.get_context()
        self.timeout = timeout
        self.workers = [self._spawn() for _ in range(n)]

    def _spawn(self):
        parent, child = self.ctx.Pipe()
        p = self.ctx.Process(target=_worker_loop, args=(child,), daemon=True)
        p.start()
        child.close()
        if not parent.poll(300):
            raise SystemExit("grading worker failed to start")
        parent.recv()
        return {"proc": p, "conn": parent, "idx": None, "deadline": None}

    def _kill(self, w):
        try:
            w["proc"].terminate()
            w["proc"].join(5)
            w["conn"].close()
        except Exception:
            pass

    def map(self, tasks, progress=None):
        from multiprocessing.connection import wait
        results = [None] * len(tasks)
        pending = collections.deque(range(len(tasks)))
        n_done = 0
        while n_done < len(tasks):
            for w in self.workers:
                if w["idx"] is None and pending:
                    w["idx"] = pending.popleft()
                    w["deadline"] = time.time() + self.timeout
                    w["conn"].send(tasks[w["idx"]])
            busy = [w for w in self.workers if w["idx"] is not None]
            ready = wait([w["conn"] for w in busy], timeout=1.0)
            for k, w in enumerate(self.workers):
                if w["idx"] is None:
                    continue
                res = None
                if w["conn"] in ready:
                    try:
                        status, payload = w["conn"].recv()
                        res = payload if status == "ok" else {"rule": False, "rule_units": False, "pred": [],
                                                              "gold_norm": [], "error": payload}
                    except (EOFError, OSError):
                        res = {"rule": False, "rule_units": False, "pred": [], "gold_norm": [], "error": "worker died"}
                        self._kill(w)
                        self.workers[k] = dict(self._spawn(), idx=w["idx"])
                        w = self.workers[k]
                elif time.time() > w["deadline"]:
                    res = {"rule": False, "rule_units": False, "pred": [], "gold_norm": [], "error": "timeout"}
                    idx = w["idx"]
                    self._kill(w)
                    self.workers[k] = dict(self._spawn(), idx=idx)
                    w = self.workers[k]
                if res is not None:
                    results[w["idx"]] = res
                    w["idx"] = None
                    n_done += 1
                    if progress and n_done % progress == 0:
                        log("  graded %d/%d" % (n_done, len(tasks)))
        return results

    def close(self):
        for w in self.workers:
            try:
                w["conn"].send(None)
            except Exception:
                pass
            self._kill(w)


def latest_generations(workdir, run, bench):
    """Last record per uid whose settings match the run's settings."""
    meta = read_json(P(run_dir(workdir, run), "meta.json"), {}) or {}
    h = meta.get("cfg_hash")
    out = {}
    for r in read_jsonl(P(run_dir(workdir, run), "gen_%s.jsonl" % bench)):
        if h is None or r.get("cfg_hash") == h:
            out[r["uid"]] = r
    return out


def cmd_grade(a):
    wd = a.workdir
    runs = list_runs(wd, a.run)
    ensure_repos()
    pool = None
    for run in runs:
        for b in BENCHES:
            gens = latest_generations(wd, run, b)
            if not gens:
                continue
            items = {it["uid"]: it for it in load_items(wd, b)}
            path = P(run_dir(wd, run), "graded_%s.jsonl" % b)
            old = {r["uid"]: r for r in read_jsonl(path)} if not a.force else {}
            rows, tasks, slots = [], [], []
            for uid, g in gens.items():
                it = items.get(uid)
                if it is None:
                    continue
                comp_sha = sha1(g["completion"])[:12]
                if uid in old and old[uid].get("comp_sha") == comp_sha:
                    rows.append(old[uid])
                    continue
                think, ans, closed = split_thinking(g["completion"], g.get("prompt_opens_think", False))
                row = {"uid": uid, "bench": b, "run": run, "comp_sha": comp_sha, "answer": ans,
                       "has_final": bool(ans.strip()), "think_closed": closed,
                       "has_boxed": "\\boxed" in ans, "finish_reason": g.get("finish_reason"),
                       "n_new_tokens": g.get("n_new_tokens", 0), "n_think_tokens": g.get("n_think_tokens", 0),
                       "n_prompt_tokens": g.get("n_prompt_tokens", 0), "batch_seconds": g.get("batch_seconds", 0),
                       "batch_size": g.get("batch_size", 1)}
                rows.append(row)
                if b in ("ugphysics", "math500"):
                    tasks.append({"workdir": wd, "answer": ans, "gold": it["gold"],
                                  "precision": UG_PRECISION if b == "ugphysics" else 1e-8,
                                  "try_units": b == "ugphysics" and it.get("answer_type") == "NV"})
                    slots.append(row)
            if tasks:
                log("%s / %s: grading %d answers (%d reused)" % (run, b, len(tasks), len(rows) - len(tasks)))
                if pool is None:
                    pool = GradePool(a.workers, a.timeout)
                for row, res in zip(slots, pool.map(tasks, progress=500)):
                    row.update(res)
            else:
                log("%s / %s: %d answers, nothing new to grade" % (run, b, len(rows)))
            write_jsonl(path, rows)
            if b != "physicseval":
                k = sum(1 for r in rows if r.get("rule"))
                log("  rule-based accuracy so far: %d/%d = %.1f%%" % (k, len(rows), 100.0 * k / max(len(rows), 1)))
    if pool:
        pool.close()


def list_runs(workdir, only=None):
    if only:
        return [r.strip() for r in only.split(",") if r.strip()]
    base = P(workdir, "runs")
    if not os.path.isdir(base):
        return []
    return sorted(d for d in os.listdir(base) if os.path.exists(P(base, d, "meta.json")))


# --------------------------------------------------------------------------------------
# Optional LLM judge (any OpenAI-compatible chat completions endpoint)
# --------------------------------------------------------------------------------------

class JudgeStop(Exception):
    pass


def chat_once(base_url, api_key, model, prompt, max_tokens, json_mode=False, timeout=240):
    import requests
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": "Bearer " + api_key, "Content-Type": "application/json"}
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.0,
            "max_tokens": max_tokens}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    r = requests.post(url, headers=headers, json=body, timeout=timeout)
    if r.status_code == 400:  # some models reject temperature / max_tokens / response_format
        r = requests.post(url, headers=headers, timeout=timeout,
                          json={"model": model, "messages": body["messages"]})
    if r.status_code in (401, 403):
        raise JudgeStop("the judge API rejected the key (HTTP %d): %s" % (r.status_code, r.text[:200]))
    if r.status_code == 404:
        raise JudgeStop("judge model or URL not found (HTTP 404): %s" % r.text[:200])
    if r.status_code != 200:
        return None, r.status_code, r.text[:200]
    try:
        return r.json()["choices"][0]["message"]["content"] or "", 200, ""
    except Exception:
        return None, 200, "unexpected response: " + r.text[:200]


def parse_marj(text):
    seg = text.split("## Justification")[0].split("## Equivalence Judgement")[-1]
    m = re.search(r"\b(TRUE|FALSE)\b", seg.upper())
    if not m:
        m = re.search(r"\b(TRUE|FALSE)\b", text.upper())
    return None if not m else (m.group(1) == "TRUE")


def parse_rubric(text):
    cand = [text]
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.I)
    if m:
        cand.append(m.group(1))
    m = re.search(r"(\{[\s\S]*\})", text)
    if m:
        cand.append(m.group(1))
    for c in cand:
        try:
            d = json.loads(c)
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        try:
            sc = {k: float(d[k]) for k in PE_DIMS5 + [PE_OVERALL]}
        except Exception:
            continue
        if all(1 <= sc[k] <= 5 for k in PE_DIMS5) and 0 <= sc[PE_OVERALL] <= 10:
            return sc
    return None


def judge_jobs(workdir, run, max_chars):
    """Everything that still needs an LLM verdict for this run."""
    jobs = []
    rd = run_dir(workdir, run)
    # UGPhysics second stage: only answers the rule judge rejected, exactly as in the official pipeline.
    graded = read_jsonl(P(rd, "graded_ugphysics.jsonl"))
    if graded:
        items = {it["uid"]: it for it in load_items(workdir, "ugphysics")}
        tpl_path = os.path.join(ug_repo_dir(workdir), "data", "judge_prompt.txt")
        with open(tpl_path, "r", encoding="utf-8") as f:
            tpl = f.read()
        for g in graded:
            if g.get("rule") or not g.get("has_final") or not [p for p in g.get("pred", []) if str(p).strip()]:
                continue
            it = items[g["uid"]]
            prompt = (tpl.replace("{{problem}}", it["problem"]).replace("{{RS}}", it["solution"])
                      .replace("{{RA}}", ", ".join(g.get("gold_norm") or [it["gold"]]))
                      .replace("{{SS}}", g["answer"][-max_chars:]).replace("{{SA}}", ", ".join(map(str, g["pred"]))))
            jobs.append({"uid": g["uid"], "bench": "ugphysics", "comp_sha": g["comp_sha"], "prompt": prompt,
                         "kind": "marj"})
    graded = read_jsonl(P(rd, "graded_physicseval.jsonl"))
    if graded:
        items = {it["uid"]: it for it in load_items(workdir, "physicseval")}
        make = pe_rubric_prompt_fn(workdir)
        for g in graded:
            if not g.get("has_final"):
                continue  # no answer at all: scored at the rubric minimum without a call
            it = items[g["uid"]]
            jobs.append({"uid": g["uid"], "bench": "physicseval", "comp_sha": g["comp_sha"], "kind": "rubric",
                         "prompt": make(it["problem_id"], it["solution"][:40000], g["answer"][-max_chars:])})
    return jobs


def cmd_judge(a):
    wd = a.workdir
    base = a.base_url or os.environ.get("JUDGE_BASE_URL", "")
    key = a.api_key or os.environ.get("JUDGE_API_KEY", "")
    model = a.judge_model or os.environ.get("JUDGE_MODEL", "")
    runs = list_runs(wd, a.run)
    ensure_repos()
    plan = []
    for run in runs:
        for b in ("ugphysics", "physicseval"):
            done = {(r["uid"], r["comp_sha"]) for r in read_jsonl(P(run_dir(wd, run), "judge_%s.jsonl" % b))
                    if r.get("verdict") is not None and (not model or r.get("judge_model") == model)}
            jobs = [j for j in judge_jobs(wd, run, a.max_solution_chars) if j["bench"] == b]
            todo = [j for j in jobs if (j["uid"], j["comp_sha"]) not in done]
            log("%-22s %-12s judge calls needed %5d | done %5d | to do %5d"
                % (run, b, len(jobs), len(jobs) - len(todo), len(todo)))
            plan.append((run, b, todo))
    total = sum(len(t) for _, _, t in plan)
    chars = sum(len(j["prompt"]) for _, _, t in plan for j in t)
    log("\nTotal judge calls still to make: %d (about %.1f million input tokens)" % (total, chars / 4 / 1e6))
    if a.dry_run or total == 0:
        return
    if not (base and key and model):
        raise SystemExit("Set JUDGE_BASE_URL, JUDGE_API_KEY and JUDGE_MODEL (or pass --base-url/--api-key/--judge-model).")
    import threading
    from concurrent.futures import ThreadPoolExecutor
    lock, state = threading.Lock(), {"calls": 0, "fails": 0, "stop": None, "last": 0.0}
    gap = 60.0 / max(a.rpm, 1)

    def work(run, b, job):
        if state["stop"]:
            return
        for attempt in range(a.retries):
            with lock:
                if a.max_calls and state["calls"] >= a.max_calls:
                    state["stop"] = "reached --max-calls"
                    return
                wait_s = state["last"] + gap - time.time()
                state["last"] = max(time.time(), state["last"] + gap)
                state["calls"] += 1
            if wait_s > 0:
                time.sleep(wait_s)
            try:
                text, code, err = chat_once(base, key, model, job["prompt"], a.max_tokens, job["kind"] == "rubric")
            except JudgeStop as e:
                state["stop"] = str(e)
                return
            except Exception as e:
                text, code, err = None, -1, repr(e)[:200]
            verdict = None
            if text:
                verdict = parse_marj(text) if job["kind"] == "marj" else parse_rubric(text)
            if verdict is not None:
                with lock:
                    state["fails"] = 0
                    append_jsonl(P(run_dir(wd, run), "judge_%s.jsonl" % b), [{
                        "uid": job["uid"], "comp_sha": job["comp_sha"], "judge_model": model, "verdict": verdict,
                        "raw": text[:4000], "ts": now()}])
                return
            with lock:
                state["fails"] += 1
                if state["fails"] >= 8:
                    state["stop"] = "8 failures in a row (last: HTTP %s %s). Probably the quota or rate limit." % (code, err)
                    return
            time.sleep(min(90, 5 * 2 ** attempt) if code in (429, 500, 502, 503, 529, -1) else 1)

    for run, b, todo in plan:
        if not todo or state["stop"]:
            continue
        log("judging %s / %s with %s ..." % (run, b, model))
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            for k, _ in enumerate(ex.map(lambda j: work(run, b, j), todo)):
                if (k + 1) % 50 == 0:
                    log("  %d/%d" % (k + 1, len(todo)))
    if state["stop"]:
        log("\nStopped: %s\nProgress is saved; run this step again to continue." % state["stop"])
    else:
        log("\nJudging finished.")


# --------------------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------------------

def pct(x):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else "%.1f" % (100 * x)


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def ug_type(it):
    t = str(it.get("answer_type", "")).replace(" ", "")
    if it.get("is_multiple_answer") or "," in t:
        return "multiple answers"
    return {"MC": "MC (multiple choice)", "TF": "TF (true/false)", "NV": "NV (number)", "EX": "EX (expression)",
            "EQ": "EQ (equation)", "IN": "IN (interval)", "TUP": "TUP (tuple)"}.get(t, t or "?")


def load_run_bench(workdir, run, bench, judge_model=None):
    """Join items + graded answers + judge verdicts for one run and benchmark."""
    rd = run_dir(workdir, run)
    graded = {r["uid"]: r for r in read_jsonl(P(rd, "graded_%s.jsonl" % bench))}
    if not graded:
        return None
    items = load_items(workdir, bench)
    judge = {}
    for r in read_jsonl(P(rd, "judge_%s.jsonl" % bench)):
        if judge_model and r.get("judge_model") != judge_model:
            continue
        judge[(r["uid"], r["comp_sha"])] = r
    meta = read_json(P(rd, "meta.json"), {}) or {}
    per = meta.get("plan", {}).get(bench, 0)
    plan_uids = [it["uid"] for it in planned(items, per)]
    rows = []
    for it in items:
        g = graded.get(it["uid"])
        if g is None:
            continue
        row = dict(g)
        row["item"] = it
        row["stratum"] = it["stratum"]
        jv = judge.get((g["uid"], g["comp_sha"]))
        if bench == "ugphysics":
            need = (not g.get("rule")) and g.get("has_final") and bool([p for p in g.get("pred", []) if str(p).strip()])
            row["need_judge"] = need
            row["judged"] = (not need) or jv is not None
            row["marj"] = bool(g.get("rule")) or bool(jv and jv["verdict"] is True)
            row["marj_hi"] = row["marj"] or (need and jv is None)
        elif bench == "physicseval":
            if not g.get("has_final"):
                row["rubric"] = dict({k: 1.0 for k in PE_DIMS5}, **{PE_OVERALL: 0.0})
                row["judged"] = True
            else:
                row["rubric"] = jv["verdict"] if jv else None
                row["judged"] = jv is not None
        rows.append(row)
    sizes = collections.Counter(it["stratum"] for it in items)
    return {"rows": rows, "sizes": dict(sizes), "n_plan": len(plan_uids),
            "complete": set(plan_uids) <= set(graded), "meta": meta, "plan_uids": set(plan_uids)}


def acc_block(rows, key, sizes):
    """Counts plus the estimate of full-benchmark accuracy (groups weighted by their real size)."""
    n = len(rows)
    k = sum(1 for r in rows if r.get(key))
    by = collections.defaultdict(list)
    for r in rows:
        by[r["stratum"]].append(1.0 if r.get(key) else 0.0)
    lo, hi = stratified_bootstrap(by, sizes)
    return {"n": n, "k": k, "raw": k / n if n else float("nan"), "wilson": wilson(k, n),
            "weighted": weighted_mean(by, sizes), "ci": (lo, hi),
            "macro": sum(sum(v) / len(v) for v in by.values()) / len(by) if by else float("nan")}


def breakdown(rows, keyfn, valfn):
    by = collections.defaultdict(list)
    for r in rows:
        by[keyfn(r)].append(valfn(r))
    out = []
    for g in sorted(by, key=str):
        v = [x for x in by[g] if x is not None]
        out.append((g, len(by[g]), len(v), (sum(v) / len(v)) if v else float("nan")))
    return out


def gen_stats(rows):
    toks = [r.get("n_new_tokens", 0) for r in rows]
    fr = collections.Counter(r.get("finish_reason") for r in rows)
    n = max(len(rows), 1)
    secs = sum(r.get("batch_seconds", 0) / max(r.get("batch_size", 1), 1) for r in rows)
    think = sum(r.get("n_think_tokens", 0) for r in rows)
    return {"n": len(rows), "mean_new_tokens": sum(toks) / n, "median_new_tokens": quantile(toks, 0.5),
            "p90_new_tokens": quantile(toks, 0.9), "think_share": think / max(sum(toks), 1),
            "stop": fr.get("stop", 0) / n, "length": fr.get("length", 0) / n, "loop": fr.get("loop", 0) / n,
            "no_final": sum(1 for r in rows if not r.get("has_final")) / n,
            "no_boxed": sum(1 for r in rows if not r.get("has_boxed")) / n,
            "tok_per_s": sum(toks) / secs if secs else float("nan"), "gpu_hours": secs / 3600}


def head_to_head(ra, rb, valfn, sizes, binary):
    a = {r["uid"]: r for r in ra}
    b = {r["uid"]: r for r in rb}
    common = [u for u in a if u in b and valfn(a[u]) is not None and valfn(b[u]) is not None]
    if not common:
        return None
    da, db, dd = (collections.defaultdict(list) for _ in range(3))
    wins = losses = 0
    for u in common:
        x, y = float(valfn(a[u])), float(valfn(b[u]))
        s = a[u]["stratum"]
        da[s].append(x)
        db[s].append(y)
        dd[s].append(x - y)
        wins += x > y
        losses += y > x
    diff = weighted_mean(dd, sizes)
    lo, hi = stratified_bootstrap(dd, sizes)
    return {"n": len(common), "a": weighted_mean(da, sizes), "b": weighted_mean(db, sizes), "diff": diff,
            "ci": (lo, hi), "a_only": wins, "b_only": losses,
            "p": mcnemar_exact(wins, losses) if binary else None,
            "significant": bool(lo > 0 or hi < 0)}


def cmd_report(a):
    wd = a.workdir
    runs = list_runs(wd, a.run)
    out_dir = P(wd, "results")
    os.makedirs(P(out_dir, "tables"), exist_ok=True)
    data = {run: {b: load_run_bench(wd, run, b, a.judge_model) for b in BENCHES} for run in runs}
    runs = [r for r in runs if any(data[r].values())]
    if not runs:
        raise SystemExit("Nothing graded yet. Run generate and grade first.")
    md, js = [], {"generated": now(), "harness_version": VERSION, "runs": {}, "head_to_head": []}
    md.append("# Physics baseline evaluation\n\nGenerated %s. Every run gets the same questions and prompts.\n" % now())

    md.append("## Runs\n")
    rows = []
    for run in runs:
        m = next(d["meta"] for d in data[run].values() if d)
        c, info = m.get("cfg", {}), m.get("info", {})
        rows.append([run, c.get("model"), json.dumps(c.get("template_kwargs", {})), c.get("max_new_tokens"),
                     c.get("repetition_penalty"), info.get("dtype"), info.get("gpu"),
                     (info.get("model_commit") or "")[:8], m.get("padding", {}).get("safe", "n/a")])
        js["runs"][run] = {"meta": m, "benchmarks": {}}
    md.append(md_table(["run", "model", "chat-template options", "max new tokens", "repetition penalty", "dtype",
                        "GPU", "model commit", "padding-safe"], rows))
    keys = ("max_new_tokens", "repetition_penalty", "temperature", "loop_stop")
    if len({tuple(js["runs"][r]["meta"].get("cfg", {}).get(k) for k in keys) for r in runs}) > 1:
        md.append("\n**WARNING: these runs do not share the same decoding settings (see the table). "
                  "Only compare runs with identical settings, or say clearly that they differ.**")
    if any((js["runs"][r]["meta"].get("backend") == "mock") for r in runs):
        md.append("\n**WARNING: at least one run used the mock backend. Its numbers are fabricated test data.**")

    # ---------------- UGPhysics ----------------
    ug = {r: data[r]["ugphysics"] for r in runs if data[r]["ugphysics"]}
    if ug:
        md.append("\n## UGPhysics (English)\n")
        md.append("Accuracy is the estimate for the full %d-problem English set: each subject is weighted by "
                  "its real size. `rule` = official rule-based judge only (no API). `rule+units` also accepts a "
                  "correct number that carries a unit inside the box (diagnostic). `MARJ` = official two-stage "
                  "protocol, rule judge then LLM judge.\n" % sum(next(iter(ug.values()))["sizes"].values()))
        rows = []
        for run, d in ug.items():
            R, S = d["rows"], d["sizes"]
            rule, units = acc_block(R, "rule", S), acc_block(R, "rule_units", S)
            auto = [r for r in R if ug_type(r["item"])[:2] in ("MC", "TF", "NV")]
            need = sum(1 for r in R if r.get("need_judge"))
            judged = sum(1 for r in R if r.get("need_judge") and r["judged"])
            marj = acc_block(R, "marj", S) if (judged == need and (judged or not need)) else None
            lo_hi = (acc_block(R, "marj", S)["weighted"], acc_block(R, "marj_hi", S)["weighted"])
            if need and judged == 0:
                marj_txt = "not run"
            elif marj:
                marj_txt = "%s [%s, %s]" % (pct(marj["weighted"]), pct(marj["ci"][0]), pct(marj["ci"][1]))
            else:
                marj_txt = "partial: between %s and %s (%d/%d judged)" % (pct(lo_hi[0]), pct(lo_hi[1]), judged, need)
            rows.append([run, "%d / %d%s" % (len(R), d["n_plan"], "" if d["complete"] else " INCOMPLETE"),
                         "%s [%s, %s]" % (pct(rule["weighted"]), pct(rule["ci"][0]), pct(rule["ci"][1])),
                         pct(rule["raw"]), pct(rule["macro"]), pct(units["weighted"]),
                         pct(sum(1 for r in auto if r.get("rule")) / len(auto)) if auto else "n/a", marj_txt,
                         "%d" % sum(1 for r in R if r.get("error"))])
            js["runs"][run]["benchmarks"]["ugphysics"] = {
                "n": len(R), "n_planned": d["n_plan"], "complete": d["complete"], "rule": rule,
                "rule_units": units, "marj": marj, "marj_bounds": lo_hi, "judge_needed": need,
                "judge_done": judged, "generation": gen_stats(R)}
        md.append(md_table(["run", "items done / planned", "rule accuracy % [95% CI]", "unweighted %",
                            "macro over subjects %", "rule+units %", "MC/TF/NV only %", "MARJ % [95% CI]",
                            "grader errors"], rows))
        for title, keyfn in (("subject", lambda r: r["stratum"]), ("domain", lambda r: r["item"].get("domain")),
                             ("reasoning skill", lambda r: r["item"].get("level")),
                             ("answer type", lambda r: ug_type(r["item"]))):
            md.append("\n### Rule accuracy by %s (%%)\n" % title)
            tabs = {run: {g: (n, v) for g, n, _, v in breakdown(d["rows"], keyfn, lambda r: 1.0 if r.get("rule") else 0.0)}
                    for run, d in ug.items()}
            groups = sorted({g for t in tabs.values() for g in t}, key=str)
            rows = [[g, max(t.get(g, (0, 0))[0] for t in tabs.values())] +
                    [pct(tabs[run][g][1]) if g in tabs[run] else "-" for run in ug] for g in groups]
            md.append(md_table([title, "items"] + list(ug), rows))
            with open(P(out_dir, "tables", "ugphysics_by_%s.csv" % title.replace(" ", "_")), "w", newline="") as f:
                csv.writer(f).writerows([[title, "items"] + list(ug)] + rows)

    # ---------------- PhysicsEval ----------------
    pe = {r: data[r]["physicseval"] for r in runs if data[r]["physicseval"]}
    if pe:
        md.append("\n## PhysicsEval (test split)\n")
        md.append("Free-text answers, graded only by the LLM judge with the official rubric: six 1-5 scores and "
                  "an overall correctness score from 0 to 10. Answers with no final text get the minimum.\n")
        rows = []
        for run, d in pe.items():
            R, S = d["rows"], d["sizes"]
            J = [r for r in R if r.get("rubric")]
            entry = {"n": len(R), "n_planned": d["n_plan"], "complete": d["complete"], "judged": len(J),
                     "generation": gen_stats(R)}
            if J and len(J) == len(R):
                by = collections.defaultdict(list)
                for r in J:
                    by[r["stratum"]].append(r["rubric"][PE_OVERALL])
                ov, ci = weighted_mean(by, S), stratified_bootstrap(by, S)
                dims = [sum(r["rubric"][k] for r in J) / len(J) for k in PE_DIMS5]
                good = sum(1 for r in J if r["rubric"][PE_OVERALL] >= 8) / len(J)
                entry.update({"overall": ov, "overall_ci": ci, "share_8plus": good, "dims": dict(zip(PE_DIMS5, dims))})
                rows.append([run, "%d / %d%s" % (len(R), d["n_plan"], "" if d["complete"] else " INCOMPLETE"),
                             "%.2f [%.2f, %.2f]" % (ov, ci[0], ci[1]), pct(good)] + ["%.2f" % x for x in dims])
            else:
                rows.append([run, "%d / %d%s" % (len(R), d["n_plan"], "" if d["complete"] else " INCOMPLETE"),
                             "needs the judge step (%d/%d judged)" % (len(J), len(R)), "-"] + ["-"] * 6)
            js["runs"][run]["benchmarks"]["physicseval"] = entry
        md.append(md_table(["run", "items done / planned", "overall correctness 0-10 [95% CI]", "share scoring 8+ %"]
                           + [k.replace("_", " ") for k in PE_DIMS5], rows))
        done = {run: d for run, d in pe.items() if all(r.get("rubric") for r in d["rows"])}
        if done:
            for title, keyfn in (("category", lambda r: r["stratum"]),
                                 ("difficulty band", lambda r: r["item"].get("difficulty_band"))):
                md.append("\n### Overall correctness by %s (0-10)\n" % title)
                tabs = {run: {g: (n, v) for g, n, _, v in breakdown(d["rows"], keyfn, lambda r: r["rubric"][PE_OVERALL])}
                        for run, d in done.items()}
                groups = sorted({g for t in tabs.values() for g in t}, key=str)
                rows = [[g, max(t.get(g, (0, 0))[0] for t in tabs.values())] +
                        ["%.2f" % tabs[run][g][1] if g in tabs[run] else "-" for run in done] for g in groups]
                md.append(md_table([title, "items"] + list(done), rows))

    # ---------------- MATH-500 ----------------
    mt = {r: data[r]["math500"] for r in runs if data[r]["math500"]}
    if mt:
        md.append("\n## MATH-500 (regression check)\n")
        md.append("Graded with the same rule judge. Use it to compare runs with each other, not with published "
                  "MATH-500 numbers, which use a different grader.\n")
        rows = []
        for run, d in mt.items():
            blk = acc_block(d["rows"], "rule", d["sizes"])
            rows.append([run, "%d / %d%s" % (len(d["rows"]), d["n_plan"], "" if d["complete"] else " INCOMPLETE"),
                         "%s [%s, %s]" % (pct(blk["weighted"]), pct(blk["ci"][0]), pct(blk["ci"][1])), pct(blk["raw"])])
            js["runs"][run]["benchmarks"]["math500"] = {"n": len(d["rows"]), "n_planned": d["n_plan"],
                                                        "complete": d["complete"], "rule": blk,
                                                        "generation": gen_stats(d["rows"])}
        md.append(md_table(["run", "items done / planned", "accuracy % [95% CI]", "unweighted %"], rows))
        for title, keyfn in (("subject", lambda r: r["stratum"]), ("level", lambda r: r["item"].get("level"))):
            md.append("\n### Accuracy by %s (%%)\n" % title)
            tabs = {run: {g: (n, v) for g, n, _, v in breakdown(d["rows"], keyfn, lambda r: 1.0 if r.get("rule") else 0.0)}
                    for run, d in mt.items()}
            groups = sorted({g for t in tabs.values() for g in t}, key=str)
            md.append(md_table([title, "items"] + list(mt),
                               [[g, max(t.get(g, (0, 0))[0] for t in tabs.values())] +
                                [pct(tabs[run][g][1]) if g in tabs[run] else "-" for run in mt] for g in groups]))

    # ---------------- generation behaviour ----------------
    md.append("\n## Generation behaviour\n")
    md.append("`hit token limit` and `stuck in a loop` answers are almost always wrong. `no final answer` means the "
              "model never left its thinking section. If these rates differ a lot between runs, the accuracy gap is "
              "partly a budget or looping problem, not physics. If a model loops on more than about 5% of questions, "
              "also test it under a new run name with `--repetition-penalty 1.05` and treat its better "
              "configuration as the score to beat.\n")
    rows = []
    for run in runs:
        for b in BENCHES:
            d = data[run][b]
            if not d:
                continue
            g = gen_stats(d["rows"])
            rows.append([run, b, g["n"], "%.0f" % g["mean_new_tokens"], "%.0f" % g["median_new_tokens"],
                         "%.0f" % g["p90_new_tokens"], pct(g["think_share"]), pct(g["stop"]), pct(g["length"]),
                         pct(g["loop"]), pct(g["no_final"]), pct(g["no_boxed"]) if b != "physicseval" else "-",
                         "%.0f" % g["tok_per_s"] if not math.isnan(g["tok_per_s"]) else "n/a", "%.2f" % g["gpu_hours"]])
    md.append(md_table(["run", "benchmark", "items", "mean new tokens", "median", "p90", "thinking share %",
                        "finished normally %", "hit token limit %", "stuck in a loop %", "no final answer %",
                        "no boxed answer %", "tokens/s", "GPU hours"], rows))

    # ---------------- head to head ----------------
    md.append("\n## Head-to-head\n")
    md.append("Compared on the items both runs answered. The difference is A minus B with a paired bootstrap 95% "
              "interval; it is significant when the interval excludes zero. `p` is the exact McNemar test.\n")
    rows = []
    specs = [("ugphysics", "rule accuracy", lambda r: 1.0 if r.get("rule") else 0.0, True, 100),
             ("ugphysics", "rule+units accuracy", lambda r: 1.0 if r.get("rule_units") else 0.0, True, 100),
             ("ugphysics", "MARJ accuracy", lambda r: (1.0 if r.get("marj") else 0.0) if r.get("judged") else None, True, 100),
             ("physicseval", "overall correctness", lambda r: r["rubric"][PE_OVERALL] if r.get("rubric") else None, False, 1),
             ("math500", "accuracy", lambda r: 1.0 if r.get("rule") else 0.0, True, 100)]
    for i in range(len(runs)):
        for k in range(i + 1, len(runs)):
            A, B = runs[i], runs[k]
            for b, name, fn, binary, scale in specs:
                da, db = data[A][b], data[B][b]
                if not da or not db:
                    continue
                if name == "MARJ accuracy" and not (all(r["judged"] for r in da["rows"]) and all(r["judged"] for r in db["rows"])):
                    continue
                h = head_to_head(da["rows"], db["rows"], fn, da["sizes"], binary)
                if not h or (name == "overall correctness" and h["n"] < min(len(da["rows"]), len(db["rows"]))):
                    continue
                same = ({r["uid"] for r in da["rows"]} == {r["uid"] for r in db["rows"]}) and da["complete"] and db["complete"]
                verdict = ("A better" if h["diff"] > 0 else "B better") if h["significant"] else "no significant difference"
                fmt = (lambda x: "%.1f" % (x * scale)) if scale == 100 else (lambda x: "%.2f" % x)
                rows.append([A, B, b, name, h["n"], fmt(h["a"]), fmt(h["b"]),
                             "%s [%s, %s]" % (("%+.1f" % (h["diff"] * scale)) if scale == 100 else "%+.2f" % h["diff"],
                                              fmt(h["ci"][0]), fmt(h["ci"][1])),
                             h["a_only"], h["b_only"], "%.4f" % h["p"] if h["p"] is not None else "-",
                             verdict + ("" if same else " (item sets differ or incomplete)")])
                js["head_to_head"].append(dict(h, A=A, B=B, bench=b, metric=name, same_items=same, verdict=verdict))
    if rows:
        md.append(md_table(["A", "B", "benchmark", "metric", "common items", "A", "B", "A - B [95% CI]",
                            "A better on", "B better on", "p", "verdict"], rows))
    else:
        md.append("Needs at least two graded runs.")

    # ---------------- which base is ahead ----------------
    md.append("\n## Which model is ahead\n")
    lines = []
    for b, label, metrics in (("ugphysics", "UGPhysics", ["MARJ accuracy", "rule accuracy"]),
                              ("physicseval", "PhysicsEval", ["overall correctness"]),
                              ("math500", "MATH-500", ["accuracy"])):
        for metric in metrics:
            hs = [h for h in js["head_to_head"] if h["bench"] == b and h["metric"] == metric]
            names = sorted({h["A"] for h in hs} | {h["B"] for h in hs})
            if len(names) < len([r for r in runs if data[r][b]]) or not hs:
                continue  # this metric is not available for every run yet
            score = {}
            for h in hs:
                score[h["A"]], score[h["B"]] = h["a"], h["b"]
            order = sorted(score, key=score.get, reverse=True)
            top = order[0]
            beaten = [o for o in order[1:] if any(h["significant"] and {h["A"], h["B"]} == {top, o} for h in hs)]
            tied = [o for o in order[1:] if o not in beaten]
            unit = (lambda x: "%.2f/10" % x) if b == "physicseval" else (lambda x: "%.1f%%" % (100 * x))
            msg = "- **%s (%s):** `%s` leads with %s." % (label, metric, top, unit(score[top]))
            if tied:
                msg += " Its lead over %s is within the margin of error." % ", ".join("`%s`" % t for t in tied)
            if beaten:
                msg += " It is significantly ahead of %s." % ", ".join("`%s`" % t for t in beaten)
            if not all(h["same_items"] for h in hs):
                msg += " (Some runs are incomplete, so this is provisional.)"
            lines.append(msg)
            break
    md.append("\n".join(lines) if lines else "Needs at least two graded runs.")

    # ---------------- per-item export ----------------
    for b in BENCHES:
        have = [r for r in runs if data[r][b]]
        if not have:
            continue
        uids = sorted({row["uid"] for r in have for row in data[r][b]["rows"]})
        look = {r: {row["uid"]: row for row in data[r][b]["rows"]} for r in have}
        with open(P(out_dir, "items_%s.csv" % b), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            cols = ["rule", "rule_units", "marj", "finish_reason", "n_new_tokens", "pred"] if b != "physicseval" \
                else ["overall_correctness", "finish_reason", "n_new_tokens"]
            w.writerow(["uid", "group", "gold"] + ["%s:%s" % (r, c) for r in have for c in cols])
            for u in uids:
                first = next(look[r][u] for r in have if u in look[r])
                line = [u, first["stratum"], json.dumps(first["item"]["gold"], ensure_ascii=False)[:300]]
                for r in have:
                    row = look[r].get(u)
                    for c in cols:
                        if row is None:
                            line.append("")
                        elif c == "overall_correctness":
                            line.append(row["rubric"][PE_OVERALL] if row.get("rubric") else "")
                        elif c == "pred":
                            line.append(", ".join(map(str, row.get("pred", [])))[:200])
                        else:
                            line.append(row.get(c, ""))
                w.writerow(line)

    text = "\n".join(md) + "\n"
    with open(P(out_dir, "summary.md"), "w", encoding="utf-8") as f:
        f.write(text)
    write_json(P(out_dir, "summary.json"), js)
    log(text)
    log("Saved: %s, summary.json, items_*.csv and tables/ in %s" % (P(out_dir, "summary.md"), out_dir))


# --------------------------------------------------------------------------------------
# Self-test of the grading stack
# --------------------------------------------------------------------------------------

def cmd_selftest(a):
    wd = a.workdir
    ensure_repos()
    ok = True

    def check(name, got, want):
        nonlocal ok
        good = got == want
        ok = ok and good
        log("  %-4s %s" % ("ok" if good else "FAIL", name) + ("" if good else "   got %r, expected %r" % (got, want)))

    log("1. LaTeX parser")
    try:
        from sympy.parsing.latex import parse_latex
        check("parse_latex", str(parse_latex(r"\frac{1}{2} m v^2")) != "", True)
    except Exception as e:
        ok = False
        log("  FAIL parse_latex: %s\n  Fix: pip install antlr4-python3-runtime==4.11.1  (must match sympy)" % repr(e)[:200])
    log("2. Official UGPhysics rule judge")
    pool = GradePool(1, 120)
    cases = [
        (r"So the final answer is \boxed{4.39 \times 10^{3}}.", r"\boxed{4390}", True, True),
        (r"\boxed{C}", r"\boxed{C}", True, True), (r"\boxed{B}", r"\boxed{C}", False, False),
        (r"\boxed{False}", r"\boxed{No}", True, True), (r"\boxed{2.21}", r"\boxed{2.2}", True, True),
        (r"\boxed{2.5}", r"\boxed{2.2}", False, False),
        (r"\boxed{\frac{\hbar^{2}\pi^{2}}{2 R^{2} m}}", r"\boxed{\frac{\pi^{2} \hbar^{2}}{2 m R^{2}}}", True, True),
        (r"\boxed{574.2, 0.0732}", r"\boxed{0.0732, 574.2}", True, True),
        (r"\boxed{13.06 \text{ eV}}", r"\boxed{13.06}", False, True),
        (r"\boxed{2.78 \, \mathrm{m}^2}", r"\boxed{2.78}", False, True),
        (r"\boxed{7.5 \text{ eV}}", r"\boxed{13.06}", False, False),
        (r"I could not finish.", r"\boxed{5}", False, False), ("", r"\boxed{5}", False, False),
    ]
    res = pool.map([{"workdir": wd, "answer": p, "gold": g, "precision": UG_PRECISION, "try_units": True}
                    for p, g, _, _ in cases])
    pool.close()
    for (p, g, w_rule, w_units), r in zip(cases, res):
        check("%-48s vs %-28s" % (p[:48], g[:28]), (r["rule"], r["rule_units"]), (w_rule, w_units))
    log("3. Thinking split, loop detector, statistics")
    check("per-group range", parse_per_group("ugphysics=100:200,math500=30"), {"ugphysics": [100, 200], "math500": 30})
    _its = [{"rank": k} for k in range(250)]
    check("planned range", (len(planned(_its, [100, 200])), len(planned(_its, 100)), len(planned(_its, 0))), (100, 100, 250))
    check("split closed", split_thinking("<think>a</think> b", False), ("a", "b", True))
    check("split open (tag in prompt)", split_thinking("still thinking", True), ("still thinking", "", False))
    check("split open (tag in text)", split_thinking("<think>hm", False), ("hm", "", False))
    check("split none", split_thinking("answer", False), ("", "answer", True))
    check("loop detected", detect_loop(list(range(50)) + [7, 8, 9] * 60), True)
    check("no loop in normal text", detect_loop([i % 97 for i in range(600)]), False)
    check("zeros in a number are not a loop", detect_loop(list(range(300)) + [0] * 12), False)
    check("mcnemar", round(mcnemar_exact(10, 2), 4), 0.0386)
    check("wilson", tuple(round(x, 3) for x in wilson(50, 100)), (0.404, 0.596))
    check("exact batching", plan_batches([0, 1, 2, 3, 4], [5, 5, 5, 4, 4], 2, True), [[0, 1], [2], [3, 4]])
    check("marj parse", parse_marj("## Equivalence Judgement\n**TRUE**\n## Justification\nfine"), True)
    check("rubric parse", parse_rubric('```json\n{"problem_id":"x","mathematical_accuracy":4,"logical_consistency":4,'
                                       '"completeness":5,"clarity_and_coherence":4,"formulas_principles":4,'
                                       '"assumptions_made":3,"overall_correctness":7}\n```')[PE_OVERALL], 7.0)
    log("\nSELF-TEST " + ("PASSED" if ok else "FAILED - fix the items marked FAIL before trusting any score"))
    if not ok:
        sys.exit(1)


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--workdir", required=True, help="project folder (on Google Drive)")
        return p

    p = common(sub.add_parser("selftest"))
    p.set_defaults(fn=cmd_selftest)

    p = common(sub.add_parser("prepare"))
    p.add_argument("--benchmarks", default=",".join(BENCHES))
    p.add_argument("--force", action="store_true")
    p.add_argument("--ugphysics-dir", help="local copy of the dataset: <dir>/<Subject>/en.jsonl")
    p.add_argument("--physicseval-file", help="local test.json")
    p.add_argument("--math500-file", help="local jsonl with problem/answer/subject/level/unique_id")
    p.set_defaults(fn=cmd_prepare)

    p = common(sub.add_parser("generate"))
    p.add_argument("--run", required=True, help="one of: %s, or a new name with --model" % ", ".join(RUNS))
    p.add_argument("--model")
    p.add_argument("--adapter", help="optional LoRA adapter (merged before generation)")
    p.add_argument("--enable-thinking", help="true/false; passed to the chat template")
    p.add_argument("--benchmarks", default=",".join(BENCHES))
    p.add_argument("--per-group", default="", help="e.g. ugphysics=100,physicseval=25,math500=30 (0 or absent = all)")
    p.add_argument("--max-new-tokens", type=int, default=GEN_DEFAULTS["max_new_tokens"])
    p.add_argument("--repetition-penalty", type=float, default=GEN_DEFAULTS["repetition_penalty"])
    p.add_argument("--temperature", type=float, default=GEN_DEFAULTS["temperature"])
    p.add_argument("--no-loop-stop", action="store_true")
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--batching", choices=["auto", "padded", "exact"], default="auto")
    p.add_argument("--dtype", default="auto", choices=["auto", "float16", "bfloat16", "float32"])
    p.add_argument("--backend", choices=["hf", "mock"], default="hf")
    p.add_argument("--smoke", action="store_true", help="few items, prints prompt/answer/speed, saves nothing permanent")
    p.add_argument("--max-items", type=int, default=0)
    p.add_argument("--time-budget-min", type=float, default=0)
    p.set_defaults(fn=cmd_generate)

    p = common(sub.add_parser("grade"))
    p.add_argument("--run", help="comma-separated; default all runs")
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--timeout", type=float, default=120)
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_grade)

    p = common(sub.add_parser("judge"))
    p.add_argument("--run")
    p.add_argument("--base-url")
    p.add_argument("--api-key")
    p.add_argument("--judge-model")
    p.add_argument("--rpm", type=float, default=10)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--max-calls", type=int, default=0)
    p.add_argument("--max-tokens", type=int, default=4096)
    p.add_argument("--retries", type=int, default=4)
    p.add_argument("--max-solution-chars", type=int, default=12000)
    p.add_argument("--dry-run", action="store_true", help="only count the calls that would be made")
    p.set_defaults(fn=cmd_judge)

    p = common(sub.add_parser("report"))
    p.add_argument("--run")
    p.add_argument("--judge-model", help="only use verdicts from this judge model")
    p.set_defaults(fn=cmd_report)

    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
