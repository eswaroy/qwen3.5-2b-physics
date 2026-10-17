#!/usr/bin/env python3
"""
physdata.py - Phase 2: build thinking-trace training data for LFM2.5-1.2B-Thinking (CPU only).

Why the data looks the way it does (from the baseline report):
  * 61% of UGPhysics answers hit the 4,096-token limit and 49% never left the thinking section.
    So every training example has a COMPLETE, SHORT reasoning trace that ends in a final answer.
  * Every example keeps a thinking trace (training on bare question -> answer pairs damages a
    thinking model). The trainer wraps it in the model's own <think> ... </think> format.
  * The answer section ends exactly the way each exam asks (boxed, unit outside the box).
  * MegaScience was decontaminated against MATH-500, GPQA, MMLU etc. but NOT against UGPhysics or
    PhysicsEval, and both come from university textbooks. So we remove anything resembling an exam
    question ourselves (exact match, shared 13-word runs, TF-IDF similarity).

New in 1.1 (after reading the v1 stats.md and samples.md):
  * Subjects follow the exam. v1 was 34% classical mechanics and 4% quantum mechanics; the exam is 15% and
    19%. Physics questions are tagged by a small classifier trained on the UGPhysics DEV questions (it is
    compared with the old keyword tagger by cross-validation and the better one is used) and sampled with
    per-subject quotas proportional to exam share x weakness.
  * More physics for the thin subjects: physics questions from MegaScience's NaturalReasoning part, found
    by a physics-vs-other classifier trained on MegaScience's own subject labels. Only rows with a
    reference answer are used, so every boxed answer can be checked.
  * Answer summaries use only clean equation lines (v1 wrapped prose and bullet lines in $...$).
  * The grader check also compares the solution's answer in normalised form ("v = 5 m/s" -> 5) and
    handles multi-part answers. Failures are listed in grader_drops.csv; results are cached on Drive.
  * Drops questions that need a missing figure, table or handbook case, and maths proofs. Physics
    "show that" questions become free-form (plain) examples.

Sources
  MegaScience/MegaScience  (CC-BY-NC-SA-4.0)  physics rows (41,410, TextbookReasoning) + a maths sample
                           + NaturalReasoning physics rows + Nemotron-Science physics multiple choice
  IUTVanguard/PhysicsEval  (CC-BY-SA-4.0)     train split (17,647)

Commands
  inspect   stream a few rows of every source and print their real format
  build     build train.jsonl / val.jsonl / stats.md / samples.md / leak_report.csv / grader_drops.csv

Needs physeval.py in the same folder (it reuses the official UGPhysics prompt builder and grader).
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
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import physeval as PE  # noqa: E402

VERSION = "1.2"
SEED = 20261008
MODEL_ID = "LiquidAI/LFM2.5-1.2B-Thinking"
MEGASCIENCE = "MegaScience/MegaScience"
PHYSICSEVAL = "IUTVanguard/PhysicsEval"

# Share of the final training set per style. A style that runs short is refilled from "ug".
MIX = {"ug": 0.70, "plain": 0.12, "math": 0.10, "knowledge": 0.05, "pe": 0.03}
UG_SYSTEMS = [PE.UG_SYSTEM, "You are a helpful assistant trained by Liquid AI.", None]
UG_SYSTEM_WEIGHTS = [0.6, 0.2, 0.2]
OPENERS = [
    "Let me identify the physical setup and the laws that apply, then solve it step by step.\n\n",
    "First I'll note what is given and what is asked, then choose the governing principles.\n\n",
    "Let me set up the physical model before calculating.\n\n",
    "",
]
PERSONA = re.compile(
    r"^\s*(?:certainly|okay|ok|alright|absolutely|excellent|great|sure|ah|well|hello|of course)\b[^\n]*\n+"
    r"|^\s*(?:as a|i am a|i'm a)\s+(?:professor|teacher|physicist)[^\n]*\n+"
    r"|^\s*let'?s break (?:it|this) down[^\n]*\n+", re.I)
DEV_RANK = 100          # UGPhysics items with rank < 100 in their subject = dev set; the rest is the final test
NEG_SUBJECTS = ["chemistry", "biology", "medicine", "cs", "economics"]
# Questions that cannot be answered from their text alone (figure, table or handbook case not included).
MISSING_CONTEXT = re.compile(
    r"\bfig(?:ure)?s?\.?\s*\(?\d"
    r"|\b(?:in|from|see) the (?:accompanying |following |given |above |below )?(?:figure|diagram|graph|plot|chart|sketch)\b"
    r"|\b(?:figure|diagram|graph|sketch) (?:below|above|shown)\b"
    r"|\bshown (?:in the (?:figure|diagram|graph|circuit|sketch)|below|above)\b"
    r"|\b(?:in|see) the (?:accompanying |following |given |above |below )?table\b"
    r"|\b(?:accompanying|following|given) table\b|\btables?\s+\d"
    r"|\bcase\s+\d+[a-z]\b|\broark", re.I)
PROOF = re.compile(r"^\s*(?:prove|show that|show how|demonstrate that|verify that)\b", re.I)

# UGPhysics subjects -> keywords (lowercase substrings). Order = tie-break priority (specific first).
TOPICS = [
    ("SemiconductorPhysics", "Semiconductor Physics", ["semiconductor", "p-n junction", "pn junction", "doping", "donor",
                                                        "acceptor", "band gap", "bandgap", "carrier concentration",
                                                        "transistor", "diode", "depletion", "hole mobility"]),
    ("Solid-StatePhysics", "Solid-State Physics", ["lattice", "crystal", "phonon", "brillouin", "reciprocal lattice",
                                                    "band structure", "fermi energy", "debye", "bloch", "unit cell",
                                                    "miller", "bravais"]),
    ("StatisticalMechanics", "Statistical Mechanics", ["partition function", "boltzmann factor", "fermi-dirac",
                                                        "bose-einstein", "canonical ensemble", "microstate",
                                                        "density of states", "chemical potential", "grand canonical",
                                                        "maxwell-boltzmann", "ensemble"]),
    ("Relativity", "Relativity", ["relativistic", "lorentz transformation", "special relativity", "time dilation",
                                  "length contraction", "four-vector", "four-momentum", "spacetime", "proper time",
                                  "rest frame", "rapidity", "invariant mass"]),
    ("Electrodynamics", "Electrodynamics", ["maxwell's equations", "maxwell equations", "electromagnetic wave",
                                            "poynting", "vector potential", "retarded", "radiated power", "waveguide",
                                            "gauge", "plasma frequency", "skin depth", "larmor", "dipole radiation"]),
    ("TheoreticalMechanics", "Theoretical Mechanics", ["lagrangian", "hamiltonian", "generalized coordinate",
                                                        "euler-lagrange", "canonical transformation", "poisson bracket",
                                                        "principle of least action", "virtual work", "euler angles",
                                                        "normal mode", "small oscillations", "rigid body"]),
    ("GeometricalOptics", "Geometrical Optics", ["lens", "mirror", "focal", "refraction", "snell", "image distance",
                                                  "magnification", "prism", "telescope", "microscope", "refractive"]),
    ("WaveOptics", "Wave Optics", ["interference", "diffraction", "slit", "grating", "polariz", "coherence",
                                   "thin film", "fringe", "fresnel", "fraunhofer", "huygens"]),
    ("QuantumMechanics", "Quantum Mechanics", ["schrödinger", "schrodinger", "wave function", "wavefunction",
                                               "eigenvalue", "eigenstate", "commutator", "expectation value",
                                               "perturbation", "tunneling", "infinite well", "quantum harmonic",
                                               "spin-1/2", "operator", "uncertainty principle"]),
    ("AtomicPhysics", "Atomic Physics", ["atom", "hydrogen", "bohr", "spectral line", "zeeman", "fine structure",
                                         "nucleus", "nuclear", "half-life", "decay", "x-ray", "rydberg", "isotope",
                                         "photoelectric", "compton"]),
    ("Thermodynamics", "Thermodynamics", ["entropy", "heat engine", "carnot", "isothermal", "adiabatic", "ideal gas",
                                          "first law", "second law", "enthalpy", "heat capacity", "specific heat",
                                          "thermal", "temperature", "refrigerator", "calorimet"]),
    ("ClassicalElectromagnetism", "Classical Electromagnetism", ["electric field", "magnetic field", "charge",
                                                                  "capacitor", "capacitance", "resistor", "current",
                                                                  "voltage", "inductor", "inductance", "gauss's law",
                                                                  "ampere", "faraday", "coulomb", "circuit", "emf",
                                                                  "magnetic flux", "solenoid", "dielectric"]),
    ("ClassicalMechanics", "Classical Mechanics", ["force", "friction", "velocity", "acceleration", "momentum",
                                                   "collision", "projectile", "pulley", "incline", "spring", "torque",
                                                   "angular momentum", "moment of inertia", "pendulum", "kinetic energy",
                                                   "work done", "gravitational", "orbit", "mass"]),
]
PHYSICS_WORDS = sorted({k for _, _, ks in TOPICS for k in ks if len(k) > 5})
# One of these is enough for a NaturalReasoning row to be considered (the classifier decides afterwards).
STRONG_PHYSICS = ["quantum", "photon", "electron", "proton", "neutron", "hamiltonian", "lagrangian", "entropy",
                  "boltzmann", "partition function", "wave function", "wavefunction", "schrödinger", "schrodinger",
                  "relativistic", "lorentz", "magnetic", "electric field", "velocity", "acceleration", "momentum",
                  "kinetic energy", "potential energy", "thermodynamic", "torque", "friction", "oscillat",
                  "wavelength", "refract", "diffract", "interference", "semiconductor", "phonon", "fermi", "bose",
                  "nuclear", "radioactive", "gravitational", "planck", "\\hbar", "photoelectric", "capacitor",
                  "inductor", "resistor", "voltage", "joule", "kelvin", "pendulum", "projectile", "harmonic oscillator",
                  "angular momentum", "electromagnetic", "polariz", "optical", "lens", "laser", "plasma",
                  "superconduct", "blackbody", "black body", "ideal gas", "heat engine", "carnot", "adiabatic",
                  "isothermal", "spin-1/2", "eigenstate", "zeeman", "hydrogen atom", "bohr", "debye", "lattice"]


def log(*a):
    print(*a, flush=True)


def sha(s):
    return hashlib.sha1(s.encode("utf-8", "replace")).hexdigest()


# --------------------------------------------------------------------------------------
# Text helpers
# --------------------------------------------------------------------------------------

def norm_words(text):
    t = re.sub(r"\\[a-zA-Z]+", " ", text.lower())
    return re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", t)


def norm_key(text):
    return " ".join(norm_words(text))


def bucket(feature, n_buckets):
    """Stable feature hash (Python's hash() changes between runs, which made v1 builds slightly irreproducible)."""
    return zlib.crc32(feature.encode("utf-8")) & (n_buckets - 1)


def tag_topic(text):
    low = text.lower()
    best, best_score = None, 0
    for key, _, kws in TOPICS:
        score = sum(1 for k in kws if k in low)
        if score > best_score:
            best, best_score = key, score
    return best


def topic_name(key):
    for k, name, _ in TOPICS:
        if k == key:
            return name
    return "Physics"


def boxed_contents(text):
    out, i = [], 0
    while True:
        i = text.find("\\boxed{", i)
        if i < 0:
            return out
        j, depth = i + 7, 1
        while j < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[j], 0)
            j += 1
        if depth:
            return out
        out.append((i, j, text[i + 7:j - 1]))
        i = j


def unbox(text):
    """Replace every \\boxed{X} by X (the box belongs in the answer section, not the thinking)."""
    spans = boxed_contents(text)
    for i, j, inner in reversed(spans):
        text = text[:i] + inner + text[j:]
    return text


UNI = [("²", "^{2}"), ("³", "^{3}"), ("⁻¹", "^{-1}"), ("⁻²", "^{-2}"), ("⁻³", "^{-3}"), ("⁴", "^{4}"),
       ("×", " \\times "), ("·", " \\cdot "), ("−", "-"), ("–", "-"), ("\u00a0", " ")]


def clean_ref(ref):
    r = (ref or "").strip()
    for a, b in UNI:
        r = r.replace(a, b)
    r = re.sub(r"(?<=\d)\s*[x]\s*10\s*\^", r" \\times 10^", r)   # 1.5 x 10^3
    r = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", r)                    # 15,000 -> 15000
    r = re.sub(r"\\[,;:! ]|~", " ", r)                                   # LaTeX spaces (\, is not a list comma)
    spans = boxed_contents(r)
    if spans:
        r = spans[-1][2]
    r = r.strip().strip("$").strip()
    r = re.sub(r"^\\\(|\\\)$|^\\\[|\\\]$", "", r).strip()
    r = re.sub(r"^(?:the\s+)?(?:final\s+)?answer\s*(?:is|:)\s*", "", r, flags=re.I).strip()
    return r.rstrip(".").strip()


def split_top_level(s, seps=(",", ";")):
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch in seps and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur.strip())
    return parts


_NUM_FULL = re.compile(r"^\s*" + PE._NUM + r"\s*$")
_LHS = re.compile(r"^\s*\$?[A-Za-z\\][\w\\{}^_,' ]{0,25}\$?\s*(?:=|\\approx|≈)\s*(.+)$")


def split_number_unit(s):
    """'3.2 m/s' -> ('3.2', 'm/s'); '4.2 \\times 10^{-3} \\text{ J}' -> ('4.2 \\times 10^{-3}', 'J'); else None."""
    m = re.match(PE._NUM, s)
    if not m or not m.group(0).strip():
        return None
    num, rest = m.group(0).strip(), s[m.end():].strip()
    if not rest:
        return num, ""
    probe = "\\boxed{" + s + "}"
    if PE.strip_units(probe) is None:
        return None
    unit = re.sub(r"\\(?:text|mathrm|textrm|mathit|operatorname)\s*\{([^{}]*)\}", r"\1", rest)
    unit = re.sub(r"\\[,;!: ]|~", " ", unit).strip()
    return num, unit


def mathy(s):
    words = [w for w in re.findall(r"(?<!\\)\b[A-Za-z]{4,}\b", s)]
    return len(words) <= 1 and bool(re.search(r"[\\^_=+\-*/()]|\d|\b[a-zA-Z]\b", s))


def has_options(q):
    return len(re.findall(r"(?:^|\s|\()\(?([A-E])[\).:]\s", q)) >= 2


def classify(ref, question):
    """-> (answer_type, box_items, units) or ('TEXT', None, None)."""
    r = clean_ref(ref)
    if not r or len(r) > 160:
        return "TEXT", None, None
    m = re.fullmatch(r"\(([A-J])\)(?:\s+.*)?|([A-J])(?:[.:)](?:\s*.*)?)?", r)   # "B", "(B) circle", "B. circle"
    if m and has_options(question):
        return "MC", [m.group(1) or m.group(2)], [""]
    low = r.lower().strip(" .")
    if low in ("yes", "no", "true", "false"):
        return "TF", [{"yes": "True", "no": "False"}.get(low, low.capitalize())], [""]
    lettered = re.split(r"\(([a-h])\)", r.replace("**", ""))
    if len(lettered) >= 5 and not lettered[0].strip() and lettered[1] == "a" and lettered[3] == "b":
        parts = [p.strip(" ,;.") for p in lettered[2::2]]          # "(a) 0 m/s (b) 2.3 m/s"
        parts = [p for p in parts if p] if all(parts) else []
    elif ("," in r or ";" in r) and not _NUM_FULL.match(r.replace(",", "")):
        parts = split_top_level(r)
    else:
        parts = [r]
    if not parts:
        return "TEXT", None, None
    if 2 <= len(parts) <= 4:
        types, items, units = [], [], []
        for p in parts:
            t, it, u = classify(p, question)
            if t not in ("NV", "EX", "EQ"):
                return "TEXT", None, None
            types.append(t)
            items += it
            units += u
        return ", ".join(types), items, units
    if len(parts) > 4:
        return "TEXT", None, None
    nu = split_number_unit(r)
    if nu is None:
        m = _LHS.match(r)  # "v = 5 m/s"
        if m:
            nu = split_number_unit(m.group(1).strip().strip("$"))
    if nu:
        return "NV", [nu[0]], [nu[1]]
    if len(r) <= 120 and mathy(r):
        m = re.fullmatch(r"(.+?)\s*\\(?:text|mathrm)\s*\{\s*([A-Za-z][A-Za-z0-9/^{}\-\s\\]{0,12})\}", r)
        g = m.group(1).strip() if m else ""
        if m and mathy(g) and g.count("{") == g.count("}") and not re.search(r"[\\_^]$", g):  # unit outside the box
            return ("EQ" if "=" in m.group(1) else "EX"), [m.group(1).strip()], [m.group(2).strip()]
        return ("EQ" if "=" in r else "EX"), [r], [""]
    return "TEXT", None, None


_DISPLAY = re.compile(r"^(?:\$\$(.+)\$\$|\\\[(.+)\\\]|\$(.+)\$|\\\((.+)\\\))$")
_RELATION = re.compile(r"=|\\approx|\\Rightarrow|\\implies|\\simeq|\\equiv|\\propto")
_TEXT_CMD = re.compile(r"\\(?:text|mathrm|textrm|operatorname|mathbf|mathit|textit|textbf)\s*\{[^{}]*\}")


def key_lines(solution, k=2):
    """The last k clean equation lines of a solution, each as $...$ (for the short answer section).

    Only lines that are pure maths are used: a whole line in $...$, $$...$$, \\[...\\] or \\(...\\), or the bare
    middle line of a display block. Lines mixing prose and inline maths, list items with prose, aligned
    environments and lines without a relation (=, \\approx, ...) are skipped. No equation line -> ""."""
    out = []
    for raw in reversed(solution.splitlines()):
        line = unbox(raw).strip()
        line = re.sub(r"^(?:[-*•]\s+|\d{1,2}[.)]\s+)", "", line).strip()   # list markers
        if not line or len(line) > 220:
            continue
        m = _DISPLAY.match(line)
        inner = next(g for g in m.groups() if g) if m else line
        inner = inner.strip()
        if re.search(r"\$|\\\(|\\\)|\\\[|\\\]", inner):      # prose with inline maths, or several pieces
            continue
        if not _RELATION.search(inner) or re.search(r"\\(?:begin|end)\b|&", inner):
            continue
        bare = _TEXT_CMD.sub(" ", inner)
        if re.search(r"(?<![\\A-Za-z])[A-Za-z]{4,}", bare):    # a plain word of 4+ letters = prose
            continue
        if any(len(re.findall(r"[A-Za-z]{3,}", t)) >= 2 for t in re.findall(r"\\text\w*\s*\{([^{}]*)\}", inner)):
            continue                                            # a sentence hidden inside \text{...}
        if bare.count("{") != bare.count("}"):
            continue
        inner = re.sub(r"\\\\\s*$", "", inner).rstrip(" ,.;:").strip()
        if not inner or "$%s$" % inner in out:
            continue
        out.append("$%s$" % inner)
        if len(out) == k:
            break
    return "\n".join(reversed(out))


def answer_line(items, units, multiple):
    box = "\\boxed{%s}" % ", ".join(items)
    us = [u for u in units if u]
    if not us:
        return "So the final answer is %s." % box
    if not multiple:
        return "So the final answer is %s %s." % (box, us[0])
    return "So the final answer is %s (units: %s)." % (box, ", ".join(u or "none" for u in units))


def clean_solution(text):
    t = (text or "").replace("\r\n", "\n").strip()
    for _ in range(3):
        t2 = PERSONA.sub("", t, count=1)
        if t2 == t:
            break
        t = t2.strip()
    t = re.sub(r"<\/?think>", "", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


# --------------------------------------------------------------------------------------
# Loading sources
# --------------------------------------------------------------------------------------

def iter_megascience(local_file=None):
    if local_file:
        for r in PE.read_jsonl(local_file):
            yield r
        return
    from datasets import load_dataset
    ds = load_dataset(MEGASCIENCE, split="train", streaming=True)
    for r in ds:
        yield r


def load_physicseval_train(local_file=None):
    if local_file:
        if local_file.endswith(".json"):
            with open(local_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return PE.read_jsonl(local_file)
    from datasets import load_dataset
    return [dict(r) for r in load_dataset(PHYSICSEVAL, split="train")]


def is_physics_text(q):
    low = q.lower()
    return sum(1 for w in PHYSICS_WORDS if w in low) >= 2


def physics_prefilter(q):
    low = q.lower()
    return any(w in low for w in STRONG_PHYSICS) or is_physics_text(q)


class Reservoir:
    """Keeps a uniform random sample of at most k items from a stream."""

    def __init__(self, k, rnd):
        self.k, self.rnd, self.seen, self.items = k, rnd, 0, []

    def add(self, x):
        self.seen += 1
        if len(self.items) < self.k:
            self.items.append(x)
        else:
            j = self.rnd.randrange(self.seen)
            if j < self.k:
                self.items[j] = x


def collect_megascience(cache_dir, local_file, limit, math_keep, nemo_keep):
    """One streaming pass over MegaScience; keeps physics, a maths sample and physics MCQs. Cached on Drive."""
    out_path = os.path.join(cache_dir, "megascience_selected.jsonl")
    if os.path.exists(out_path) and not limit:
        rows = PE.read_jsonl(out_path)
        log("  megascience (textbook physics, maths, Nemotron): %d cached rows" % len(rows))
        return rows
    rnd = random.Random(SEED)
    phys, maths, nemo = [], Reservoir(math_keep, rnd), Reservoir(nemo_keep, rnd)
    t0 = time.time()
    for n, r in enumerate(iter_megascience(local_file)):
        if limit and n >= limit:
            break
        subj, src = (r.get("subject") or ""), (r.get("source") or "")
        if subj == "physics":
            phys.append(r)
        elif subj == "math":
            maths.add(r)
        elif "nemo" in src and is_physics_text(r.get("question", "")):
            nemo.add(r)
        if n and n % 100000 == 0:
            log("  streamed %d rows (%.0f s): physics %d, maths seen %d, nemotron physics seen %d"
                % (n, time.time() - t0, len(phys), maths.seen, nemo.seen))
    for r in phys:
        r["_pool"] = "megascience_physics"
    for r in maths.items:
        r["_pool"] = "megascience_math"
    for r in nemo.items:
        r["_pool"] = "nemotron_physics"
    rows = phys + maths.items + nemo.items
    if not limit:
        PE.write_jsonl(out_path, rows)
    log("  megascience: kept %d physics, %d maths (of %d), %d Nemotron physics (of %d)"
        % (len(phys), len(maths.items), maths.seen, len(nemo.items), nemo.seen))
    return rows


def collect_extra(cache_dir, local_file, limit, nr_keep, neg_keep):
    """Second streaming pass (new in 1.1): NaturalReasoning rows that may be physics (with a reference answer)
    plus question-only samples of the other MegaScience subjects (they train the physics filter). Cached."""
    out_path = os.path.join(cache_dir, "megascience_extra.jsonl")
    if os.path.exists(out_path) and not limit:
        rows = PE.read_jsonl(out_path)
        log("  megascience (NaturalReasoning + other subjects): %d cached rows" % len(rows))
        return rows
    log("  streaming MegaScience once more for NaturalReasoning physics (20 to 40 minutes, cached afterwards)")
    rnd = random.Random(SEED + 1)
    nr = Reservoir(nr_keep, rnd)
    neg = {s: Reservoir(neg_keep, rnd) for s in NEG_SUBJECTS}
    t0 = time.time()
    for n, r in enumerate(iter_megascience(local_file)):
        if limit and n >= limit:
            break
        src, subj = (r.get("source") or ""), (r.get("subject") or "")
        if src == "natural_reasoning":
            if (r.get("reference_answer") or "").strip() and physics_prefilter(r.get("question") or ""):
                nr.add({"question": r.get("question"), "answer": r.get("answer"),
                        "reference_answer": r.get("reference_answer"), "source": src})
        elif subj in neg:
            neg[subj].add({"question": r.get("question"), "subject": subj})
        if n and n % 100000 == 0:
            log("  streamed %d rows (%.0f s): NaturalReasoning physics candidates %d" % (n, time.time() - t0, nr.seen))
    for r in nr.items:
        r["_pool"] = "naturalreasoning_physics"
    for s, res in neg.items():
        for r in res.items:
            r["_pool"] = "neg_" + s
    rows = nr.items + [r for res in neg.values() for r in res.items]
    if not limit:
        PE.write_jsonl(out_path, rows)
    log("  kept %d NaturalReasoning rows (of %d candidates) and %s other-subject questions"
        % (len(nr.items), nr.seen, {s: len(v.items) for s, v in neg.items()}))
    return rows


# --------------------------------------------------------------------------------------
# Topic classifiers (naive Bayes on hashed words and word pairs)
# --------------------------------------------------------------------------------------

class NaiveBayes:
    """Multinomial naive Bayes on word / word-pair presence, uniform class prior. Small, fast, no sklearn."""

    def __init__(self, n_buckets=1 << 20, alpha=0.5):
        self.n, self.alpha = n_buckets, alpha

    def _x(self, texts):
        import numpy as np
        from scipy import sparse
        rows, cols = [], []
        for i, t in enumerate(texts):
            w = norm_words(t)
            ids = {bucket(f, self.n) for f in w + [a + "_" + b for a, b in zip(w, w[1:])]}
            rows += [i] * len(ids)
            cols += ids
        return sparse.csr_matrix((np.ones(len(rows), dtype=np.float32), (rows, cols)), shape=(len(texts), self.n))

    def fit(self, texts, labels):
        import numpy as np
        self.classes = sorted(set(labels))
        x = self._x(texts)
        y = np.array([self.classes.index(l) for l in labels])
        self.w = np.zeros((self.n, len(self.classes)), dtype=np.float32)
        for k in range(len(self.classes)):
            cnt = np.asarray(x[y == k].sum(axis=0)).ravel() + self.alpha
            self.w[:, k] = np.log(cnt / cnt.sum())
        return self

    def predict(self, texts, chunk=5000):
        """-> (labels, probability of the chosen label)."""
        import numpy as np
        labels, probs = [], []
        for s in range(0, len(texts), chunk):
            sc = np.asarray(self._x(texts[s:s + chunk]).dot(self.w))
            sc -= sc.max(axis=1, keepdims=True)
            p = np.exp(sc)
            p /= p.sum(axis=1, keepdims=True)
            labels += [self.classes[i] for i in sc.argmax(axis=1)]
            probs += [float(v) for v in p.max(axis=1)]
        return labels, probs


def cv_predict(texts, labels, folds=5, seed=SEED):
    """Out-of-fold predictions (each text is predicted by a model that never saw it)."""
    idx = list(range(len(texts)))
    random.Random(seed).shuffle(idx)
    pred = [None] * len(texts)
    for f in range(folds):
        test = idx[f::folds]
        held = set(test)
        train = [i for i in idx if i not in held]
        nb = NaiveBayes().fit([texts[i] for i in train], [labels[i] for i in train])
        for i, p in zip(test, nb.predict([texts[i] for i in test])[0]):
            pred[i] = p
    return pred


def build_physics_filter(ms_rows, extra_rows, rnd):
    """Physics vs maths/chemistry/biology/medicine/cs/economics, trained on MegaScience's own subject labels."""
    groups = collections.defaultdict(list)
    for r in ms_rows:
        if r["_pool"] == "megascience_physics":
            groups["physics"].append(r["question"])
        elif r["_pool"] == "megascience_math":
            groups["math"].append(r["question"])
    for r in extra_rows:
        if r["_pool"].startswith("neg_"):
            groups[r["_pool"][4:]].append(r["question"])
    texts, labels = [], []
    for g, qs in sorted(groups.items()):
        qs = rnd.sample(qs, min(len(qs), 6000 if g == "physics" else 4000))
        texts += qs
        labels += [g] * len(qs)
    if len(groups) < 2 or "physics" not in groups:
        return None, ["physics filter: not enough labelled subjects, keyword filter only"]
    pred = cv_predict(texts, labels)
    by = collections.defaultdict(lambda: [0, 0])
    for p, l in zip(pred, labels):
        by[l][0] += 1
        by[l][1] += (p == "physics")
    rep = ["Physics filter (naive Bayes on MegaScience subject labels, 5-fold cross-validation):", "",
           "| true subject | questions | classified as physics |", "|---|---|---|"]
    for l, (n, k) in sorted(by.items(), key=lambda x: x[0] != "physics"):
        rep.append("| %s | %d | %.1f%% |" % (l, n, 100.0 * k / max(n, 1)))
    return NaiveBayes().fit(texts, labels), rep


def build_subject_tagger(ug_items):
    """UGPhysics subject from question text. Trained on the DEV questions only (rank < 100 per subject); the
    old keyword tagger is kept if it is more accurate in cross-validation."""
    dev = [it for it in ug_items if it.get("rank", 0) < DEV_RANK and it.get("problem")]
    texts, labels = [it["problem"] for it in dev], [it["stratum"] for it in dev]
    kw = [tag_topic(t) for t in texts]
    kw_acc = sum(p == l for p, l in zip(kw, labels)) / max(len(dev), 1)
    rep = ["Subject tagger (trained on %d UGPhysics dev questions; 5-fold cross-validation):" % len(dev), ""]
    if len(set(labels)) < 2:
        rep.append("too few dev questions: keyword tagger used")
        return (lambda qs: [(tag_topic(q), None) for q in qs]), "keywords", rep
    cv = cv_predict(texts, labels)
    nb_acc = sum(p == l for p, l in zip(cv, labels)) / len(dev)
    rep += ["| subject | dev questions | classifier correct | keywords correct |", "|---|---|---|---|"]
    for s in sorted(set(labels)):
        ii = [i for i, l in enumerate(labels) if l == s]
        rep.append("| %s | %d | %.0f%% | %.0f%% |" % (s, len(ii), 100.0 * sum(cv[i] == s for i in ii) / len(ii),
                                                      100.0 * sum(kw[i] == s for i in ii) / len(ii)))
    rep.append("| **all** | %d | **%.1f%%** | **%.1f%%** |" % (len(dev), 100 * nb_acc, 100 * kw_acc))
    if kw_acc > nb_acc:
        rep.append("\nThe keyword tagger was more accurate, so it is used.")
        return (lambda qs: [(tag_topic(q), None) for q in qs]), "keywords", rep
    nb = NaiveBayes().fit(texts, labels)
    rep.append("\nThe classifier is used.")

    def tag(qs):
        labs, ps = nb.predict(qs)
        return list(zip(labs, ps))
    return tag, "classifier", rep


# --------------------------------------------------------------------------------------
# Building candidate examples
# --------------------------------------------------------------------------------------

def ug_prompt(ug_utils, question, topic_key, atype, multiple):
    item = {"language": "EN", "subject": topic_name(topic_key), "answer_type": atype,
            "is_multiple_answer": multiple}
    try:
        return ug_utils.make_prompt(item) + "\n\n" + question
    except SystemExit:
        return None


def make_candidates(ms_rows, pe_rows, ug_utils, rnd):
    cands, drops = [], collections.Counter()
    for r in ms_rows:
        q, sol, ref, pool = (r.get("question") or "").strip(), r.get("answer") or "", r.get("reference_answer") or "", r["_pool"]
        if not q or not sol:
            drops["empty"] += 1
            continue
        if MISSING_CONTEXT.search(q):
            drops["needs a figure, table or handbook case"] += 1
            continue
        sol_boxes = [b for _, _, b in boxed_contents(sol)]
        if not ref and sol_boxes:
            ref = sol_boxes[-1]
        think = clean_solution(unbox(sol))
        atype, items, units = classify(ref, q)
        proof = bool(PROOF.match(q))
        topic = r.get("_topic") if pool != "megascience_math" else None
        base = {"pool": pool, "question": q, "think": think, "ref": clean_ref(ref), "atype": atype,
                "box_items": items, "units": units, "topic": topic, "topic_p": r.get("_topic_p"),
                "sol_boxes": sol_boxes, "id": "%s/%s" % (pool, sha(q)[:12])}
        if pool == "megascience_math":
            if proof:
                drops["maths proof"] += 1
                continue
            if atype == "TEXT":
                drops["math_unboxable"] += 1
                continue
            msgs = [{"role": "user", "content": q + PE.MATH_SUFFIX}]
            summary = key_lines(think)
            ans = (summary + "\n\n" if summary else "") + answer_line(items, units, "," in atype)
            cands.append(dict(base, style="math", messages=msgs, answer=ans))
            continue
        if atype == "TEXT" or proof:  # free-form answer ("show that ..." questions too: the result is given)
            ref_text = clean_ref(ref)
            if not ref_text:
                drops["no_reference"] += 1
                continue
            if len(ref_text) > 800:
                drops["reference_too_long"] += 1
                continue
            summary = key_lines(think)
            ans = (summary + "\n\n" if summary else "") + "**Answer:** " + ref_text
            cands.append(dict(base, atype="TEXT", box_items=None, units=None, style="plain",
                              messages=[{"role": "user", "content": q}], answer=ans))
            continue
        multiple = "," in atype
        style = "knowledge" if atype in ("MC", "TF") else "ug"
        if style == "ug" and rnd.random() < 0.15:
            style = "plain"
        if style == "plain":
            msgs = [{"role": "user", "content": q}]
        else:
            user = ug_prompt(ug_utils, q, topic, atype, multiple)
            if user is None:
                drops["prompt_error"] += 1
                continue
            system = rnd.choices(UG_SYSTEMS, weights=UG_SYSTEM_WEIGHTS)[0]
            msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
        summary = key_lines(think) if atype not in ("MC", "TF") else ""
        ans = (summary + "\n\n" if summary else "") + answer_line(items, units, multiple)
        cands.append(dict(base, style=style, messages=msgs, answer=ans))
    for r in pe_rows:
        q = (r.get("problem") or "").strip()
        sol = clean_solution(r.get("elaborated_solution_steps") or "")
        finals = [re.sub(r"\s*\n\s*", " ", f).strip() for f in (r.get("final_answers_in_brief") or []) if f and f.strip()]
        if not q or not sol or not finals:
            drops["pe_empty"] += 1
            continue
        if MISSING_CONTEXT.search(q):
            drops["needs a figure, table or handbook case"] += 1
            continue
        content = ("You are an expert on Physics. You solve problems step by step while maintaining logical "
                   "consistency. Solve the following Physics problem: %s"
                   "Finally, write the final answers in brief. Make sure you write all equations in LaTeX." % q)
        summary = key_lines(sol, 3)
        ans = (summary + "\n\n" if summary else "") + "**Final answers in brief:**\n" + \
            "\n".join("%d. %s" % (i + 1, f) for i, f in enumerate(finals))
        cands.append({"pool": "physicseval_train", "question": q, "think": unbox(sol), "ref": " | ".join(finals),
                      "atype": "TEXT", "box_items": None, "units": None, "topic": r.get("_topic"),
                      "topic_p": r.get("_topic_p"), "sol_boxes": [],
                      "id": "physicseval_train/%s" % r.get("Problem_ID", sha(q)[:12]), "style": "pe",
                      "messages": [{"role": "user", "content": content}], "answer": ans})
    for c in cands:
        c["think"] = rnd.choice(OPENERS) + c["think"]
    return cands, drops


# --------------------------------------------------------------------------------------
# Leak removal (decontamination) against every exam question
# --------------------------------------------------------------------------------------

def ngrams(words, n=13):
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def tfidf_matrix(docs, n_buckets=1 << 20, idf=None):
    import numpy as np
    from scipy import sparse
    rows, cols, vals = [], [], []
    for i, d in enumerate(docs):
        w = norm_words(d)
        feats = collections.Counter(w + [a + "_" + b for a, b in zip(w, w[1:])])
        for f, c in feats.items():
            rows.append(i)
            cols.append(bucket(f, n_buckets))
            vals.append(1.0 + math.log(c))
    m = sparse.csr_matrix((vals, (rows, cols)), shape=(len(docs), n_buckets), dtype=np.float32)
    m.sum_duplicates()
    if idf is None:
        df = np.bincount(m.indices, minlength=n_buckets)
        idf = np.log((1 + len(docs)) / (1 + df)).astype(np.float32) + 1.0
    m = m.multiply(idf.reshape(1, -1)).tocsr()
    norms = np.sqrt(np.asarray(m.multiply(m).sum(axis=1)).ravel())
    norms[norms == 0] = 1.0
    m = sparse.diags(1.0 / norms).dot(m).tocsr()
    return m, idf


_COMMON_NUMBERS = {str(i) for i in range(13)} | {
    "100", "1000", "180", "360", "0.5", "9.8", "9.81", "1.6", "6.63", "6.626", "9.11", "1.38", "6.02", "6.022",
    "8.85", "1.67", "8.31", "8.314", "273", "273.15", "298", "300", "2.998"}


def sig_numbers(text):
    """Numbers that identify a problem instance (no exponents, small integers or common constants)."""
    t = re.sub(r"\^\s*\{?\s*[-+]?\d+\s*\}?|[eE][-+]?\d+\b", " ", text)
    out = set()
    for x in re.findall(r"\d+(?:\.\d+)?", t):
        try:
            g = "%g" % float(x)
        except ValueError:
            continue
        if g not in _COMMON_NUMBERS:
            out.add(g)
    return out


def decontaminate(cands, tests, threshold, report_path, num_floor=0.3):
    """tests: list of (bench, uid, text). Marks c['leak'] and writes the closest matches to a CSV.
    A leak is: the same text, a shared 13-word run, TF-IDF similarity >= threshold, or (new in 1.2) similarity
    >= num_floor together with 2+ identical problem numbers (a reworded copy of the same exercise)."""
    import numpy as np
    exact = {}
    grams = {}
    for bench, uid, text in tests:
        w = norm_words(text)
        exact.setdefault(" ".join(w), (bench, uid))
        for g in ngrams(w):
            grams.setdefault(g, (bench, uid))
    log("  exam questions: %d (exact keys %d, 13-word runs %d)" % (len(tests), len(exact), len(grams)))
    test_docs = [t for _, _, t in tests]
    cand_docs = [c["question"] for c in cands]
    all_m, idf = tfidf_matrix(test_docs + cand_docs)
    tm, cm = all_m[:len(test_docs)], all_m[len(test_docs):]
    best_s = np.zeros(len(cands), dtype=np.float32)
    best_j = np.zeros(len(cands), dtype=np.int64)
    top_j = np.zeros((len(cands), 3), dtype=np.int64)
    top_s = np.zeros((len(cands), 3), dtype=np.float32)
    k3 = min(3, len(tests))
    for s in range(0, len(cands), 4000):
        sim = cm[s:s + 4000].dot(tm.T).toarray()
        best_j[s:s + 4000] = sim.argmax(axis=1)
        best_s[s:s + 4000] = sim.max(axis=1)
        idx = np.argpartition(-sim, k3 - 1, axis=1)[:, :k3]
        top_j[s:s + 4000, :k3] = idx
        top_s[s:s + 4000, :k3] = np.take_along_axis(sim, idx, axis=1)
    test_nums = {}
    reasons = collections.Counter()
    rows = []
    for i, c in enumerate(cands):
        w = norm_words(c["question"])
        why, jj = None, best_j[i]
        if " ".join(w) in exact:
            why, hit = "exact", exact[" ".join(w)]
        else:
            hit = next((grams[g] for g in ngrams(w) if g in grams), None)
            if hit:
                why = "13-word overlap"
            elif best_s[i] >= threshold:
                why, hit = "tf-idf %.2f" % best_s[i], tests[best_j[i]][:2]
            else:
                mine = None
                for j, sj in zip(top_j[i], top_s[i]):
                    if sj < num_floor:
                        continue
                    mine = sig_numbers(c["question"]) if mine is None else mine
                    if j not in test_nums:
                        test_nums[j] = sig_numbers(tests[j][2])
                    if len(mine & test_nums[j]) >= 2:
                        why, hit, jj = "numbers %.2f" % sj, tests[j][:2], j
                        break
        c["leak"] = why
        c["leak_sim"] = float(best_s[i])
        if why:
            reasons[why.split(" ")[0]] += 1
        if why or best_s[i] >= threshold - 0.1:
            tb, tu, tt = tests[jj]
            rows.append([c["id"], c["pool"], why or "kept (below threshold)", "%.3f" % best_s[i],
                         (hit or (tb, tu))[0], (hit or (tb, tu))[1], c["question"][:300], tt[:300]])
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["train_id", "pool", "decision", "tfidf_similarity", "exam", "exam_item", "train_question", "closest_exam_question"])
        w.writerows(sorted(rows, key=lambda r: -float(r[3])))
    return reasons


# --------------------------------------------------------------------------------------
# Token lengths
# --------------------------------------------------------------------------------------

class Lengths:
    def __init__(self, model_id):
        self.exact = False
        try:
            from transformers import AutoTokenizer
            self.tok = AutoTokenizer.from_pretrained(model_id)
            self.exact = True
        except Exception as e:
            log("  tokenizer unavailable (%s); estimating tokens as characters / 3.6" % type(e).__name__)
            self.tok = None

    def many(self, texts):
        if not self.exact:
            return [int(len(t) / 3.6) + 1 for t in texts]
        out = []
        for s in range(0, len(texts), 512):
            enc = self.tok(texts[s:s + 512], add_special_tokens=False)["input_ids"]
            out += [len(x) for x in enc]
        return out

    def prompt(self, msgs_list):
        if not self.exact:
            return self.many(["\n".join(m["content"] for m in msgs) for msgs in msgs_list])
        texts = [self.tok.apply_chat_template(m, tokenize=False, add_generation_prompt=True) for m in msgs_list]
        return self.many(texts)


# --------------------------------------------------------------------------------------
# Sampling: subject quotas + grader check
# --------------------------------------------------------------------------------------

def subject_weights(workdir, run="lfm25-1.2b-thinking"):
    """-> (weight per subject (weaker = more, 0.75..1.75), base accuracy per subject, note)."""
    path = os.path.join(workdir, "results", "tables", "ugphysics_by_subject.csv")
    if not os.path.exists(path):
        return {}, {}, "no baseline table found; all subjects weighted equally"
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    col = run if rows and run in rows[0] else None
    if not col:
        return {}, {}, "baseline column %r not in %s; equal weights" % (run, path)
    acc = {}
    for r in rows:
        try:
            acc[r["subject"]] = float(r[col])
        except (ValueError, KeyError):
            pass
    if not acc:
        return {}, {}, "baseline table empty; equal weights"
    mean = sum(acc.values()) / len(acc)
    w = {s: min(1.75, max(0.75, 1 + 0.5 * (mean - a) / max(mean, 1e-6))) for s, a in acc.items()}
    return w, acc, "weakness weights from the %s baseline (weaker subject = more examples)" % run


def subject_targets(workdir, ug_items, floor=0.02):
    """Target share of each subject among physics examples: exam share x weakness, at least `floor`."""
    size = collections.Counter(it["stratum"] for it in ug_items)
    total = sum(size.values()) or 1
    exam = {s: n / total for s, n in size.items()}
    weak, acc, note = subject_weights(workdir)
    raw = {s: exam[s] * weak.get(s, 1.0) for s in exam}
    z = sum(raw.values()) or 1.0
    share = {s: max(v / z, floor) for s, v in raw.items()}
    z = sum(share.values())
    return {s: v / z for s, v in share.items()}, exam, acc, note


def priority_order(items, weight_fn, rnd):
    """Weighted random order (Efraimidis-Spirakis): heavier items tend to come first."""
    keyed = [(rnd.random() ** (1.0 / max(weight_fn(it), 1e-6)), k, it) for k, it in enumerate(items)]
    keyed.sort(key=lambda x: (-x[0], x[1]))
    return [it for _, _, it in keyed]


def waterfill(total, share, cap):
    """Split `total` across strata in proportion to `share`, never giving a stratum more than `cap`;
    what a full stratum cannot take goes to the others (in proportion)."""
    alloc = {s: 0 for s in share}
    active = {s for s in share if share[s] > 0 and cap.get(s, 0) > 0}
    left = total
    while active and left > 0:
        w = sum(share[s] for s in active)
        full = {s for s in active if cap[s] - alloc[s] <= left * share[s] / w}
        if not full:
            raw = {s: left * share[s] / w for s in active}
            base = {s: int(raw[s]) for s in active}
            rest = left - sum(base.values())
            for s in sorted(active, key=lambda s: (-(raw[s] - base[s]), str(s)))[:rest]:
                base[s] += 1
            for s in active:
                alloc[s] += base[s]
            break
        for s in full:
            left -= cap[s] - alloc[s]
            alloc[s] = cap[s]
        active -= full
    return alloc


class GraderCache:
    """(answer, gold) -> passed, saved on Drive so rebuilds skip the slow symbolic grader."""

    def __init__(self, path):
        self.path, self.d, self.new = path, {}, []
        if os.path.exists(path):
            for r in PE.read_jsonl(path):
                self.d[r["k"]] = r["ok"]

    def get(self, k):
        return self.d.get(k)

    def put(self, k, ok):
        self.d[k] = ok
        self.new.append({"k": k, "ok": ok})

    def flush(self):
        if self.new:
            PE.append_jsonl(self.path, self.new)
            self.new = []


_TEXT_INNER = re.compile(r"\\(?:text|mathrm|textrm|operatorname|mathbf|mathit|textit|textbf|rm)\s*\{([^{}]*)\}")


def latex_norm(s):
    """Conservative text normal form: two answers equal after this are the same answer (no maths needed)."""
    s = _TEXT_INNER.sub(r"\1", s)
    s = re.sub(r"\\(?:left|right|displaystyle)\b|\\[,;:! ]|~|\$", "", s)
    s = re.sub(r"\\[dt]frac", r"\\frac", s).replace("\\cdot", "*").replace("\\times", "*")
    s = re.sub(r"([_^])\{([A-Za-z0-9])\}", r"\1\2", s)
    return re.sub(r"\s+", "", s).rstrip(".")


def rhs(s):
    return s.rsplit("=", 1)[1].strip() if "=" in s else None


def solution_pairs(c):
    """(solution answer, reference) pairs to compare; the item passes if any pair agrees. The solution's answer is
    tried as written, in normalised form, and for single equations by right-hand side ("E = 5 eV" vs "5")."""
    boxes, items = c.get("sol_boxes") or [], c.get("box_items") or []
    if not boxes or not items:
        return []
    n = len(items)
    raw = ", ".join(boxes[-n:]) if n > 1 and len(boxes) >= n else boxes[-1]
    gold = ", ".join(items)
    pairs = [(raw, gold)]
    _, its, _ = classify(raw, c["question"])
    if its:
        pairs.append((", ".join(its), gold))
    if n == 1:
        r_raw, r_gold = rhs(raw), rhs(gold)
        if r_raw and not r_gold:
            pairs.append((r_raw, gold))
        elif r_gold and not r_raw:
            pairs.append((raw, r_gold))
        elif r_raw and r_gold:
            pairs.append((r_raw, r_gold))
    out = []
    for a, g in pairs:
        if a.strip() and (a, g) not in out:
            out.append((a, g))
    return out


def pair_key(a, g):
    return sha("\\boxed{%s}\x00\\boxed{%s}" % (a, g))


def run_checks(cands, workdir, pool, cache, stats):
    """Sets c['grader_ok']: the solution's own answer must agree with the reference (official UGPhysics grader)."""
    pending = []
    for c in cands:
        if "grader_ok" in c:
            continue
        pairs = solution_pairs(c)
        if not pairs:
            c["grader_ok"], c["check"] = True, "unchecked"
            stats["unchecked (no boxed answer in the solution, or free-form reference)"] += 1
            continue
        c["_pairs"] = pairs
        same = [latex_norm(a) == latex_norm(g) for a, g in pairs]
        if any(same):
            c["grader_ok"], c["check"] = True, ("agrees" if same[0] else "agrees after normalising")
            stats[c["check"]] += 1
            continue
        pending.append(c)
    tasks, keys, queued = [], [], set()
    for c in pending:
        for a, g in c["_pairs"]:
            k = pair_key(a, g)
            if cache.get(k) is None and k not in queued:
                tasks.append({"workdir": workdir, "answer": "\\boxed{%s}" % a, "gold": "\\boxed{%s}" % g,
                              "precision": PE.UG_PRECISION, "try_units": True})
                keys.append(k)
                queued.add(k)
    if tasks:
        res = pool.map(tasks, progress=2000)
        for k, r in zip(keys, res):
            cache.put(k, bool(r["rule"] or r["rule_units"]))
        cache.flush()
    for c in pending:
        oks = [bool(cache.get(pair_key(a, g))) for a, g in c["_pairs"]]
        c["grader_ok"] = any(oks)
        c["check"] = "agrees" if oks[0] else ("agrees after normalising" if any(oks) else "disagrees")
        stats[c["check"]] += 1


def fill_style(strata, want, share, check):
    """strata: {key: candidates in priority order}. Checks candidates in rounds until every stratum has its
    quota of items that pass (or runs out). Quotas follow `share`; a short stratum's quota goes to the others."""
    pos = {s: 0 for s in strata}
    good = {s: [] for s in strata}
    checked = passed = 0
    for _ in range(12):
        rate = (passed + 3.0) / (checked + 4.0)
        cap = {s: len(good[s]) + int((len(strata[s]) - pos[s]) * rate) for s in strata}
        quota = waterfill(want, share, cap)
        need = {s: quota[s] - len(good[s]) for s in strata if quota[s] > len(good[s]) and pos[s] < len(strata[s])}
        if not need:
            break
        batch = []
        for s, k in need.items():
            n = int(math.ceil(k / max(rate, 0.25) * 1.1)) + 3
            take = strata[s][pos[s]:pos[s] + n]
            pos[s] += len(take)
            batch += [(s, c) for c in take]
        check([c for _, c in batch])
        for s, c in batch:
            checked += 1
            if c["grader_ok"]:
                passed += 1
                good[s].append(c)
    quota = waterfill(want, share, {s: len(good[s]) for s in strata})
    return [c for s in strata for c in good[s][:quota[s]]], quota


# --------------------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------------------

def cmd_inspect(a):
    log("== MegaScience: first rows of each source, plus the first physics rows ==")
    shown = collections.Counter()
    for n, r in enumerate(iter_megascience(a.megascience_file)):
        key = r.get("source") if r.get("subject") != "physics" else "physics"
        if shown[key] < 2:
            shown[key] += 1
            log("\n--- source=%r subject=%r" % (r.get("source"), r.get("subject")))
            log("QUESTION:", (r.get("question") or "")[:600])
            log("ANSWER (start):", (r.get("answer") or "")[:500])
            log("ANSWER (end):", (r.get("answer") or "")[-300:])
            log("REFERENCE:", repr((r.get("reference_answer") or "")[:200]))
            t, items, units = classify(r.get("reference_answer") or "", r.get("question") or "")
            log("  -> classified as %s, box %r, units %r" % (t, items, units))
        if len(shown) >= 4 and min(shown.values()) >= 2 or n >= a.limit:
            break
        if n and n % 100000 == 0:
            log("  ... streamed %d rows, seen so far: %s" % (n, dict(shown)))
    log("\n== PhysicsEval train: first row ==")
    rows = load_physicseval_train(a.physicseval_file)
    log("rows:", len(rows))
    r = rows[0]
    log("PROBLEM:", r["problem"][:500])
    log("SOLUTION (start):", r["elaborated_solution_steps"][:500])
    log("SOLUTION (cleaned start):", clean_solution(r["elaborated_solution_steps"])[:300])
    log("FINAL ANSWERS:", r["final_answers_in_brief"])


def cmd_build(a):
    wd = a.workdir
    out = os.path.join(wd, "train_data", a.name)
    cache = os.path.join(wd, "train_data", "cache")
    os.makedirs(out, exist_ok=True)
    os.makedirs(cache, exist_ok=True)
    rnd = random.Random(SEED)
    PE.ensure_repos()
    ug_utils, _ = PE.import_ug(wd, need_judge=False)
    info = {"classifiers": []}

    log("1/8 exam questions to protect")
    tests, ug_items = [], []
    for b in PE.BENCHES:
        path = os.path.join(wd, "data", "items_%s.jsonl" % b)
        if not os.path.exists(path):
            raise SystemExit("missing %s - run the evaluation notebook's prepare step in this folder first" % path)
        items = PE.read_jsonl(path)
        tests += [(b, it["uid"], it["problem"]) for it in items]
        if b == "ugphysics":
            ug_items = items

    log("2/8 loading sources")
    ms = collect_megascience(cache, a.megascience_file, a.limit_megascience, a.math_pool, a.nemotron_pool)
    extra = [] if a.no_natural_reasoning else \
        collect_extra(cache, a.megascience_file, a.limit_megascience, a.nr_pool, a.neg_pool)
    pe_path = os.path.join(cache, "physicseval_train.jsonl")
    if a.physicseval_file:
        pe_rows = load_physicseval_train(a.physicseval_file)
    elif os.path.exists(pe_path):
        pe_rows = PE.read_jsonl(pe_path)
    else:
        pe_rows = load_physicseval_train()
        PE.write_jsonl(pe_path, pe_rows)
    log("  physicseval train: %d rows" % len(pe_rows))

    log("3/8 topic classifiers")
    phys_filter, rep = build_physics_filter(ms, extra, random.Random(SEED + 2))
    info["classifiers"] += rep + [""]
    log("  " + "\n  ".join(rep))
    unlabelled = [r for r in ms if r["_pool"] == "nemotron_physics"] + \
                 [r for r in extra if r["_pool"] == "naturalreasoning_physics"]
    kept_unl = unlabelled
    if phys_filter is not None and unlabelled:
        labs, _ = phys_filter.predict([r["question"] for r in unlabelled])
        kept_unl = [r for r, l in zip(unlabelled, labs) if l == "physics"]
    filt = collections.Counter(r["_pool"] for r in kept_unl)
    tot = collections.Counter(r["_pool"] for r in unlabelled)
    note = "Kept as physics: " + ", ".join("%s %d of %d" % (p, filt[p], tot[p]) for p in sorted(tot))
    info["classifiers"] += [note, ""]
    log("  " + note)
    rows = [r for r in ms if r["_pool"] in ("megascience_physics", "megascience_math")] + kept_unl
    tagger, info["tagger"], rep = build_subject_tagger(ug_items)
    info["classifiers"] += rep
    log("  " + "\n  ".join(rep))
    to_tag = [r for r in rows if r["_pool"] != "megascience_math"] + list(pe_rows)
    tags = tagger([(r.get("question") or r.get("problem") or "") for r in to_tag])
    for r, (t, p) in zip(to_tag, tags):
        r["_topic"], r["_topic_p"] = t, (round(p, 3) if p is not None else None)

    log("4/8 building candidate examples")
    cands, drops = make_candidates(rows, pe_rows, ug_utils, rnd)
    log("  %d candidates; dropped %s" % (len(cands), dict(drops)))
    funnel = {}

    def count(name, cs):
        funnel[name] = collections.Counter(c.get("topic") for c in cs if c["style"] != "math")
    count("candidates", cands)

    log("5/8 removing anything that resembles an exam question")
    leak = decontaminate(cands, tests, a.leak_threshold, os.path.join(out, "leak_report.csv"))
    n_before = len(cands)
    cands = [c for c in cands if not c["leak"]]
    log("  removed %d of %d (%s); details in leak_report.csv" % (n_before - len(cands), n_before, dict(leak)))
    seen, uniq = set(), []
    for c in cands:
        k = norm_key(c["question"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(c)
    log("  removed %d duplicate questions" % (len(cands) - len(uniq)))
    drops["duplicate question"] = len(cands) - len(uniq)
    cands = uniq
    count("not like an exam question", cands)

    log("6/8 measuring token lengths")
    L = Lengths(a.tokenizer or MODEL_ID)
    pt = L.prompt([c["messages"] for c in cands])
    tt = L.many([c["think"] for c in cands])
    at = L.many([c["answer"] for c in cands])
    kept = []
    too_long = too_short = 0
    for c, p, t, s in zip(cands, pt, tt, at):
        c["tok_prompt"], c["tok_think"], c["tok_answer"] = p, t, s
        total = p + t + s + 8
        if total > a.max_tokens or t > a.max_think_tokens:
            too_long += 1
        elif t < (15 if c["style"] == "knowledge" else 40):
            too_short += 1
        else:
            kept.append(c)
    log("  dropped %d too long (> %d total or > %d thinking tokens), %d too short"
        % (too_long, a.max_tokens, a.max_think_tokens, too_short))
    drops["too long"], drops["too short"] = too_long, too_short
    cands = kept
    count("length ok", cands)

    log("7/8 choosing examples: subject quotas + the official grader check")
    share, exam_share, base_acc, sw_note = subject_targets(wd, ug_items)
    log("  " + sw_note)
    mean_share = 1.0 / max(len(share), 1)
    by_style = collections.defaultdict(list)
    for c in cands:
        by_style[c["style"]].append(c)
    target = {s: int(round(a.n_total * f)) for s, f in MIX.items()}
    gcache = GraderCache(os.path.join(cache, "grader_cache.jsonl"))
    log("  grader cache: %d known answers" % len(gcache.d))
    gstats = collections.Counter()
    pool = PE.GradePool(a.workers, 60)

    def check(cs):
        run_checks(cs, wd, pool, gcache, gstats)

    def weight(c):
        w = 1.3 if (c["atype"] in ("EX", "EQ") or "," in c["atype"]) else 1.0
        if solution_pairs(c):  # the solution boxes its answer, so the grader can verify it: prefer these
            w *= 1.5
        if c["style"] == "knowledge":
            w *= min(3.0, max(0.5, share.get(c.get("topic"), mean_share) / mean_share))
        return w

    chosen, quotas = {}, {}
    for s in ("pe", "knowledge", "math", "plain", "ug"):
        want = target[s]
        if s == "ug":
            want += sum(target[x] - len(chosen[x]) for x in chosen)   # refill short styles with ug
        items = priority_order(by_style.get(s, []), weight, rnd)
        if s in ("ug", "plain"):
            strata = collections.defaultdict(list)
            for c in items:
                strata[c.get("topic")].append(c)
            sh = {k: share.get(k, 0.03 if k is None else 0.0) for k in strata}
        else:
            strata, sh = {None: items}, {None: 1.0}
        chosen[s], quotas[s] = fill_style(dict(strata), want, sh, check)
        log("  %-9s %6d of %6d wanted (%d candidates)" % (s, len(chosen[s]), want, len(items)))
    pool.close()
    log("  grader check: %s" % dict(gstats))
    write_grader_drops(out, [c for c in cands if c.get("check") == "disagrees"])

    log("8/8 writing")
    final = [c for s in chosen for c in chosen[s]]
    rnd.shuffle(final)
    n_val = min(a.n_val, len(final) // 20)
    val, train = final[:n_val], final[n_val:]

    def export(c):
        return {"id": c["id"], "source": c["pool"], "style": c["style"], "messages": c["messages"],
                "think": c["think"], "answer": c["answer"],
                "meta": {"answer_type": c["atype"], "topic": c.get("topic"), "topic_p": c.get("topic_p"),
                         "reference": c["ref"][:400], "check": c.get("check"),
                         "tokens": {"prompt": c["tok_prompt"], "think": c["tok_think"], "answer": c["tok_answer"]},
                         "leak_similarity": round(c["leak_sim"], 3)}}

    PE.write_jsonl(os.path.join(out, "train.jsonl"), [export(c) for c in train])
    PE.write_jsonl(os.path.join(out, "val.jsonl"), [export(c) for c in val])
    count("chosen", train)
    checked = collections.defaultdict(collections.Counter)
    for c in cands:
        if c.get("check") in ("agrees", "agrees after normalising", "disagrees") and c["style"] != "math":
            checked[c.get("topic")][c["check"] != "disagrees"] += 1
    info.update(share=share, exam=exam_share, acc=base_acc, sw_note=sw_note, gstats=gstats, funnel=funnel,
                checked=checked)
    write_stats(out, a, train, val, L.exact, leak, n_before, drops, info)
    write_samples(out, train, rnd)
    log("\nDONE: %d training and %d validation examples in %s" % (len(train), len(val), out))
    log("Read stats.md and samples.md before training.")


def write_grader_drops(out, bad):
    with open(os.path.join(out, "grader_drops.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "pool", "style", "topic", "reference_answer", "solution_answer", "question"])
        for c in bad:
            w.writerow([c["id"], c["pool"], c["style"], c.get("topic"), c["_pairs"][0][1], " | ".join(a for a, _ in c["_pairs"]),
                        c["question"][:300]])


def pct_table(counter, total):
    return "\n".join("| %s | %d | %.1f%% |" % (k, v, 100.0 * v / max(total, 1)) for k, v in counter.most_common())


def write_stats(out, a, train, val, exact_tokens, leak, n_before, drops, info):
    def q(xs, p):
        return PE.quantile(xs, p) if xs else 0
    n = len(train)
    tok = lambda key: [c["tok_" + key] for c in train]
    tot = [c["tok_prompt"] + c["tok_think"] + c["tok_answer"] for c in train]
    phys = [c for c in train if c["style"] != "math"]
    subj = collections.Counter(c.get("topic") for c in phys)
    md = ["# Training data %s\n" % a.name,
          "Built %s with physdata.py %s. %d training and %d validation examples.\n" % (PE.now(), VERSION, n, len(val)),
          "Token counts are %s.\n" % ("exact (LFM2.5 tokenizer)" if exact_tokens else "ESTIMATED (tokenizer unavailable)"),
          "## Mix\n", "| style | items | share |", "|---|---|---|", pct_table(collections.Counter(c["style"] for c in train), n),
          "\n## Source\n", "| source | items | share |", "|---|---|---|", pct_table(collections.Counter(c["pool"] for c in train), n),
          "\n## Subjects of the physics examples vs the exam\n",
          "Target = exam share x weakness (%s), at least 2%%. Tagged by the %s.\n" % (info["sw_note"], info["tagger"]),
          "| subject | exam share | target | items | share of physics items | base accuracy |",
          "|---|---|---|---|---|---|"]
    for s in sorted(info["exam"], key=lambda s: -info["exam"][s]):
        acc = info["acc"].get(s)
        md.append("| %s | %.1f%% | %.1f%% | %d | %.1f%% | %s |" % (
            s, 100 * info["exam"][s], 100 * info["share"].get(s, 0), subj.get(s, 0), 100.0 * subj.get(s, 0) / max(len(phys), 1),
            "%.1f%%" % acc if acc is not None else "-"))
    if subj.get(None):
        md.append("| untagged | - | - | %d | %.1f%% | - |" % (subj[None], 100.0 * subj[None] / max(len(phys), 1)))
    fun = info.get("funnel", {})
    if fun:
        md += ["\nWhere each subject's examples are lost (physics styles). A subject below its target ran out of "
               "examples that pass every step.\n",
               "| subject | " + " | ".join(fun) + " | grader agrees |", "|---|" + "---|" * (len(fun) + 1)]
        for s in sorted(info["exam"], key=lambda s: -info["exam"][s]):
            ck = info["checked"].get(s, {})
            n_ck = ck.get(True, 0) + ck.get(False, 0)
            md.append("| %s | %s | %s |" % (s, " | ".join(str(fun[k].get(s, 0)) for k in fun),
                                            "%.0f%% of %d" % (100.0 * ck.get(True, 0) / n_ck, n_ck) if n_ck else "-"))
    md += ["\n## Classifiers\n"] + info["classifiers"] + [
        "\n## Answer type\n", "| type | items | share |", "|---|---|---|",
        pct_table(collections.Counter(c["atype"] if c["atype"].count(",") < 2 else "3-4 parts" for c in train), n),
        "\n## Lengths (tokens)\n", "| part | median | p90 | max |", "|---|---|---|---|"]
    for key in ("prompt", "think", "answer"):
        xs = tok(key)
        md.append("| %s | %.0f | %.0f | %d |" % (key, q(xs, .5), q(xs, .9), max(xs) if xs else 0))
    md.append("| total | %.0f | %.0f | %d |" % (q(tot, .5), q(tot, .9), max(tot) if tot else 0))
    g = info["gstats"]
    checked = g.get("agrees", 0) + g.get("agrees after normalising", 0) + g.get("disagrees", 0)
    md += ["\nThe base model's median answer on UGPhysics was 4,096 tokens (the limit). These traces are much "
           "shorter on purpose: the model should learn to finish its reasoning.\n",
           "## Grader check\n",
           "The worked solution's own boxed answer must agree with the reference answer (official UGPhysics grader).\n",
           "| result | items |", "|---|---|"] + ["| %s | %d |" % (k, v) for k, v in g.most_common()] + [
           "\n%d of %d checked items agree (%.1f%%). The ones that disagree are listed in grader_drops.csv.\n"
           % (checked - g.get("disagrees", 0), checked, 100.0 * (checked - g.get("disagrees", 0)) / max(checked, 1)),
           "## Removed\n",
           "- resembling an exam question: %d of %d candidates %s (see leak_report.csv)" % (sum(leak.values()), n_before, dict(leak)),
           "- while building: %s" % dict((k, v) for k, v in drops.items() if v),
           "\n## Settings\n", "```",
           json.dumps({k: v for k, v in vars(a).items() if k != "fn"}, indent=1, default=str), "```"]
    with open(os.path.join(out, "stats.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")


def write_samples(out, train, rnd):
    by_style, by_pool = collections.defaultdict(list), collections.defaultdict(list)
    for c in train:
        by_style[c["style"]].append(c)
        by_pool[c["pool"]].append(c)
    picks, used = [], set()
    for s, items in sorted(by_style.items()):
        for c in rnd.sample(items, min(2, len(items))):
            picks.append(c)
            used.add(id(c))
    for p, items in sorted(by_pool.items()):
        if sum(1 for c in picks if c["pool"] == p) < 2:
            rest = [c for c in items if id(c) not in used]
            for c in rnd.sample(rest, min(2, len(rest))):
                picks.append(c)
                used.add(id(c))
    md = ["# Samples (2 per style, at least 2 per source)\n", "Shown in the shape the trainer will use: prompt, then "
          "`<think>` reasoning, then the answer. Check that answers are right and that the reasoning is complete. "
          "Long reasoning is cut at 4,000 characters here only (the training file has all of it).\n"]
    for c in picks:
        md.append("---\n## %s | %s | %s | %s | check: %s\n" % (c["style"], c["pool"], c["atype"], c.get("topic"), c.get("check")))
        for m in c["messages"]:
            md.append("**%s:**\n```\n%s\n```" % (m["role"], m["content"][:3000]))
        md.append("**assistant:**\n```\n<think>\n%s\n</think>\n\n%s\n```\n" % (c["think"][:4000], c["answer"]))
    with open(os.path.join(out, "samples.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inspect")
    p.add_argument("--megascience-file")
    p.add_argument("--physicseval-file")
    p.add_argument("--limit", type=int, default=2000000, help="stop streaming after this many rows")
    p.set_defaults(fn=cmd_inspect)
    p = sub.add_parser("build")
    p.add_argument("--workdir", required=True, help="the evaluation folder (has data/items_*.jsonl and results/)")
    p.add_argument("--name", default="v1.2")
    p.add_argument("--n-total", type=int, default=30000)
    p.add_argument("--n-val", type=int, default=500)
    p.add_argument("--max-tokens", type=int, default=2048, help="prompt + thinking + answer")
    p.add_argument("--max-think-tokens", type=int, default=1600)
    p.add_argument("--leak-threshold", type=float, default=0.4, help="TF-IDF similarity that counts as a leak (0.4 catches same-problem-new-numbers variants)")
    p.add_argument("--math-pool", type=int, default=12000)
    p.add_argument("--nemotron-pool", type=int, default=6000)
    p.add_argument("--nr-pool", type=int, default=100000, help="NaturalReasoning rows kept by the second streaming pass")
    p.add_argument("--neg-pool", type=int, default=4000, help="questions kept per non-physics subject (physics filter)")
    p.add_argument("--no-natural-reasoning", action="store_true", help="skip the second pass (v1 sources only)")
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--tokenizer", help="defaults to %s" % MODEL_ID)
    p.add_argument("--megascience-file", help="local jsonl instead of streaming from Hugging Face")
    p.add_argument("--physicseval-file", help="local json/jsonl instead of downloading")
    p.add_argument("--limit-megascience", type=int, default=0, help="quick trial: stop streaming after N rows")
    p.set_defaults(fn=cmd_build)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
