# Self-distillation data self2

Built 2026-10-12 11:21:49 with physself.py 1.2 from selfgen/self2. 2437 training and 200 validation examples.

## Overview

| | value |
|---|---|
| questions answered | 9000 |
| answers generated | 18000 |
| finished normally | 40.4% |
| judged correct by the official rule judge (per answer) | 20.6% |
| correct and clean (passed the stricter checks) | 19.2% |
| questions with at least one correct answer | 23.2% |
| examples kept (one per question) | 2085 |
| examples added from self1 (math) | 552 |
| answered with the simple prompt, trained with the official one | 2085 |

## Lengths (new tokens)

| answers | median | p90 | max |
|---|---|---|---|
| all | 3584 | 3584 | 3584 |
| finished | 2204 | 3307 | 3584 |
| correct | 2015 | 3230 | 3584 |
| kept (shortest correct) | 1965 | 3167 | 3578 |

The base model's median on UGPhysics was 4,096 (the limit). Every kept example finishes, so the model learns to finish in its own style.

## By subject

| subject | questions | answers | finished | correct per answer | kept |
|---|---|---|---|---|---|
| QuantumMechanics | 1492 | 2984 | 39% | 15% | 270 |
| ClassicalMechanics | 1427 | 2854 | 39% | 23% | 389 |
| AtomicPhysics | 1150 | 2300 | 47% | 25% | 332 |
| StatisticalMechanics | 956 | 1912 | 43% | 15% | 171 |
| TheoreticalMechanics | 725 | 1450 | 34% | 11% | 103 |
| Thermodynamics | 695 | 1390 | 32% | 16% | 137 |
| ClassicalElectromagnetism | 634 | 1268 | 40% | 24% | 185 |
| WaveOptics | 466 | 932 | 39% | 20% | 113 |
| Electrodynamics | 433 | 866 | 43% | 19% | 100 |
| Relativity | 403 | 806 | 51% | 27% | 130 |
| Solid-StatePhysics | 293 | 586 | 44% | 23% | 76 |
| SemiconductorPhysics | 234 | 468 | 45% | 21% | 57 |
| GeometricalOptics | 92 | 184 | 32% | 18% | 22 |

## Styles kept

| style | examples |
|---|---|
| ug | 1783 |
| math | 552 |
| knowledge | 302 |

## Talk about the answer format in the thinking

How often a judged-correct answer's thinking discusses the answer format ("the user said", "(unit)", "in the box" ...). Answers with 8 or more mentions are dropped (--max-format-talk).

| mentions | answers |
|---|---|
| 0 | 2919 |
| 1-3 | 435 |
| 4-7 | 105 |
| 8-11 | 22 |
| 12+ | 9 |

## Not kept

- did not finish (length): 10727
- the answer is given in the question (nothing to solve): 530
- closed its thinking more than once: 138
- equation answer has a different shape than the reference: 138
- equation for a different quantity (left-hand side differs): 56
- talks about the answer format 8+ times: 31
- keeps thinking after the thinking section: 16
- did not finish (loop): 2

6915 questions had no correct answer (saved in selfgen/self2/hard_questions.jsonl for a later round).

## Settings

```
{
 "cmd": "build",
 "workdir": "/content/drive/MyDrive/physics_eval",
 "name": "self2",
 "out": "self2",
 "max_new_tokens": 3584,
 "max_answer_chars": 4000,
 "max_format_talk": 8,
 "add_from": "self1",
 "add_styles": "math",
 "n_val": 200,
 "workers": 2
}
```
