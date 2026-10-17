# Training data v1

Built 2026-10-08 06:27:25 with physdata.py 1.0. 26865 training and 500 validation examples.

Token counts are exact (LFM2.5 tokenizer).

## Mix

| style | items | share |
|---|---|---|
| ug | 18359 | 68.3% |
| plain | 3737 | 13.9% |
| math | 2951 | 11.0% |
| knowledge | 1479 | 5.5% |
| pe | 339 | 1.3% |

## Source

| source | items | share |
|---|---|---|
| megascience_physics | 22200 | 82.6% |
| megascience_math | 2951 | 11.0% |
| nemotron_physics | 1375 | 5.1% |
| physicseval_train | 339 | 1.3% |

## Answer type

| type | items | share |
|---|---|---|
| NV | 10579 | 39.4% |
| EX | 6402 | 23.8% |
| EQ | 3726 | 13.9% |
| TEXT | 3147 | 11.7% |
| MC | 1355 | 5.0% |
| EX, EX | 907 | 3.4% |
| TF | 199 | 0.7% |
| EQ, EQ | 118 | 0.4% |
| EQ, EX | 96 | 0.4% |
| EX, EX, EX | 83 | 0.3% |
| EQ, EQ, EQ | 36 | 0.1% |
| EX, EX, EX, EX | 36 | 0.1% |
| NV, NV | 32 | 0.1% |
| EX, EQ | 21 | 0.1% |
| NV, NV, NV, NV | 14 | 0.1% |
| EX, EQ, EX | 12 | 0.0% |
| NV, NV, NV | 12 | 0.0% |
| EQ, EX, EX | 10 | 0.0% |
| NV, EX | 6 | 0.0% |
| EX, EX, EX, NV | 6 | 0.0% |
| EQ, EX, EQ, EX | 5 | 0.0% |
| EQ, EQ, EX | 5 | 0.0% |
| EQ, EQ, EQ, EQ | 5 | 0.0% |
| EQ, EX, EX, EX | 5 | 0.0% |
| EX, EQ, EQ | 5 | 0.0% |
| EX, EX, EQ | 4 | 0.0% |
| NV, EX, EX | 4 | 0.0% |
| NV, EQ | 4 | 0.0% |
| NV, NV, NV, EX | 3 | 0.0% |
| EQ, NV | 3 | 0.0% |
| EX, EX, NV, EX | 2 | 0.0% |
| EQ, EX, EQ | 2 | 0.0% |
| EX, EX, NV | 2 | 0.0% |
| EQ, NV, NV | 2 | 0.0% |
| NV, NV, EX | 2 | 0.0% |
| EX, NV | 2 | 0.0% |
| EX, EX, EQ, EX | 2 | 0.0% |
| EX, EQ, EX, EQ | 1 | 0.0% |
| EQ, EX, EQ, EQ | 1 | 0.0% |
| EQ, EQ, NV | 1 | 0.0% |
| EX, EQ, EX, EX | 1 | 0.0% |
| EQ, EQ, NV, EQ | 1 | 0.0% |
| NV, EX, EX, EX | 1 | 0.0% |
| EQ, NV, EX, EX | 1 | 0.0% |
| EX, NV, EX, NV | 1 | 0.0% |
| EX, NV, NV, EX | 1 | 0.0% |
| NV, EX, NV | 1 | 0.0% |
| EQ, EQ, EQ, EX | 1 | 0.0% |

## UGPhysics subject (keyword tag)

subject weights from the lfm25-1.2b-thinking baseline (weaker subject = sampled more)

| subject | items | share |
|---|---|---|
| untagged / maths | 10616 | 39.5% |
| ClassicalMechanics | 5553 | 20.7% |
| Thermodynamics | 3648 | 13.6% |
| ClassicalElectromagnetism | 2754 | 10.3% |
| AtomicPhysics | 1267 | 4.7% |
| QuantumMechanics | 620 | 2.3% |
| GeometricalOptics | 579 | 2.2% |
| Solid-StatePhysics | 471 | 1.8% |
| WaveOptics | 300 | 1.1% |
| Relativity | 286 | 1.1% |
| TheoreticalMechanics | 207 | 0.8% |
| SemiconductorPhysics | 193 | 0.7% |
| StatisticalMechanics | 186 | 0.7% |
| Electrodynamics | 185 | 0.7% |

## Lengths (tokens)

| part | median | p90 | max |
|---|---|---|---|
| prompt | 188 | 269 | 1404 |
| think | 387 | 800 | 1600 |
| answer | 82 | 140 | 463 |
| total | 662 | 1132 | 2027 |

The base model's median answer on UGPhysics was 4,096 tokens (the limit). These traces are much shorter on purpose: the model should learn to finish its reasoning.

## Removed

- resembling an exam question: 1639 of 70093 candidates {'13-word': 789, 'tf-idf': 736, 'exact': 114} (see leak_report.csv)
- while building: {'reference_too_long': 3231, 'no_reference': 23, 'math_unboxable': 3698, 'pe_empty': 12}
- failed the grader check: {"solution's own answer disagrees with the reference": 7077}

## Settings

```
{
 "cmd": "build",
 "workdir": "/content/drive/MyDrive/physics_eval",
 "name": "v1",
 "n_total": 30000,
 "n_val": 500,
 "max_tokens": 2048,
 "max_think_tokens": 1600,
 "leak_threshold": 0.4,
 "math_pool": 12000,
 "nemotron_pool": 6000,
 "workers": 2,
 "tokenizer": null,
 "megascience_file": null,
 "physicseval_file": null,
 "limit_megascience": 0,
 "fn": "<function cmd_build at 0x785d517ff240>"
}
```
