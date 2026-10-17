# Self-distillation data self1

Built 2026-10-10 12:55:22 with physself.py 1.1 from selfgen/self1. 638 training and 70 validation examples.

## Overview

| | value |
|---|---|
| questions answered | 9000 |
| answers generated | 18000 |
| finished normally | 49.3% |
| judged correct by the official rule judge (per answer) | 15.0% |
| correct and clean (passed the stricter checks) | 6.3% |
| questions with at least one correct answer | 7.9% |
| examples kept (one per question) | 708 |

## Lengths (new tokens)

| answers | median | p90 | max |
|---|---|---|---|
| all | 3584 | 3584 | 3584 |
| finished | 2451 | 3322 | 3584 |
| correct | 1620 | 3143 | 3583 |
| kept (shortest correct) | 1722 | 3171 | 3583 |

The base model's median on UGPhysics was 4,096 (the limit). Every kept example finishes, so the model learns to finish in its own style.

## By subject

| subject | questions | answers | finished | correct per answer | kept |
|---|---|---|---|---|---|
| maths | 1350 | 2700 | 61% | 36% | 552 |
| QuantumMechanics | 1266 | 2532 | 49% | 1% | 19 |
| ClassicalMechanics | 1210 | 2420 | 42% | 1% | 31 |
| AtomicPhysics | 976 | 1952 | 52% | 1% | 16 |
| StatisticalMechanics | 811 | 1622 | 55% | 1% | 13 |
| TheoreticalMechanics | 615 | 1230 | 42% | 1% | 7 |
| Thermodynamics | 590 | 1180 | 38% | 2% | 16 |
| ClassicalElectromagnetism | 538 | 1076 | 43% | 2% | 18 |
| WaveOptics | 396 | 792 | 43% | 1% | 11 |
| Electrodynamics | 367 | 734 | 56% | 1% | 9 |
| Relativity | 342 | 684 | 59% | 1% | 6 |
| Solid-StatePhysics | 249 | 498 | 51% | 1% | 5 |
| SemiconductorPhysics | 198 | 396 | 43% | 0% | 1 |
| GeometricalOptics | 92 | 184 | 38% | 2% | 4 |

## Styles kept

| style | examples |
|---|---|
| math | 552 |
| ug | 156 |

## Talk about the answer format in the thinking

How often a judged-correct answer's thinking discusses the answer format ("the user said", "(unit)", "in the box" ...). Answers with 8 or more mentions are dropped (--max-format-talk).

| mentions | answers |
|---|---|
| 0 | 804 |
| 1-3 | 195 |
| 4-7 | 143 |
| 8-11 | 156 |
| 12+ | 1220 |

## Not kept

- did not finish (length): 9122
- closed its thinking more than once: 3732
- talks about the answer format 8+ times: 1376
- the answer is given in the question (nothing to solve): 452
- equation answer has a different shape than the reference: 87
- equation for a different quantity (left-hand side differs): 58
- keeps thinking after the thinking section: 29
- did not finish (loop): 2
- no boxed answer after the thinking: 1

8292 questions had no correct answer (saved in selfgen/self1/hard_questions.jsonl for a later round).

## Settings

```
{
 "cmd": "build",
 "workdir": "/content/drive/MyDrive/physics_eval",
 "name": "self1",
 "out": "self1",
 "max_new_tokens": 3584,
 "max_answer_chars": 4000,
 "max_format_talk": 8,
 "n_val": 200,
 "workers": 2
}
```
