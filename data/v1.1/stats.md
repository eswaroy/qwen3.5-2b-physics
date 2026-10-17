# Training data v1.1

Built 2026-10-08 14:12:56 with physdata.py 1.1. 29500 training and 500 validation examples.

Token counts are exact (LFM2.5 tokenizer).

## Mix

| style | items | share |
|---|---|---|
| ug | 21202 | 71.9% |
| plain | 3538 | 12.0% |
| math | 2958 | 10.0% |
| knowledge | 1469 | 5.0% |
| pe | 333 | 1.1% |

## Source

| source | items | share |
|---|---|---|
| megascience_physics | 17551 | 59.5% |
| naturalreasoning_physics | 7367 | 25.0% |
| megascience_math | 2958 | 10.0% |
| nemotron_physics | 1291 | 4.4% |
| physicseval_train | 333 | 1.1% |

## Subjects of the physics examples vs the exam

Target = exam share x weakness (weakness weights from the lfm25-1.2b-thinking baseline (weaker subject = more examples)), at least 2%. Tagged by the classifier.

| subject | exam share | target | items | share of physics items | base accuracy |
|---|---|---|---|---|---|
| QuantumMechanics | 18.5% | 16.4% | 2671 | 10.1% | 13.0% |
| AtomicPhysics | 16.6% | 12.7% | 1663 | 6.3% | 16.0% |
| ClassicalMechanics | 15.1% | 15.7% | 6233 | 23.5% | 10.0% |
| StatisticalMechanics | 10.1% | 10.5% | 1426 | 5.4% | 10.0% |
| ClassicalElectromagnetism | 7.1% | 7.0% | 2881 | 10.9% | 11.0% |
| Thermodynamics | 6.7% | 7.6% | 3144 | 11.8% | 8.0% |
| TheoreticalMechanics | 5.8% | 8.0% | 1591 | 6.0% | 3.0% |
| WaveOptics | 5.5% | 5.1% | 1581 | 6.0% | 12.0% |
| Relativity | 3.8% | 4.4% | 1861 | 7.0% | 7.0% |
| SemiconductorPhysics | 3.4% | 2.6% | 537 | 2.0% | 26.0% |
| Electrodynamics | 3.3% | 4.8% | 1887 | 7.1% | 2.0% |
| Solid-StatePhysics | 3.1% | 3.2% | 903 | 3.4% | 10.0% |
| GeometricalOptics | 1.1% | 2.0% | 164 | 0.6% | 6.9% |

## Classifiers

Physics filter (naive Bayes on MegaScience subject labels, 5-fold cross-validation):

| true subject | questions | classified as physics |
|---|---|---|
| physics | 6000 | 88.1% |
| biology | 4000 | 5.5% |
| chemistry | 4000 | 34.1% |
| cs | 4000 | 6.6% |
| economics | 1296 | 8.1% |
| math | 4000 | 17.1% |
| medicine | 4000 | 3.6% |

Kept as physics: naturalreasoning_physics 90154 of 100000, nemotron_physics 5096 of 6000

Subject tagger (trained on 1258 UGPhysics dev questions; 5-fold cross-validation):

| subject | dev questions | classifier correct | keywords correct |
|---|---|---|---|
| AtomicPhysics | 100 | 59% | 61% |
| ClassicalElectromagnetism | 100 | 77% | 82% |
| ClassicalMechanics | 100 | 65% | 71% |
| Electrodynamics | 100 | 82% | 31% |
| GeometricalOptics | 58 | 64% | 90% |
| QuantumMechanics | 100 | 56% | 28% |
| Relativity | 100 | 84% | 11% |
| SemiconductorPhysics | 100 | 55% | 15% |
| Solid-StatePhysics | 100 | 82% | 61% |
| StatisticalMechanics | 100 | 75% | 19% |
| TheoreticalMechanics | 100 | 73% | 26% |
| Thermodynamics | 100 | 96% | 84% |
| WaveOptics | 100 | 82% | 24% |
| **all** | 1258 | **73.4%** | **44.9%** |

The classifier is used.

## Answer type

| type | items | share |
|---|---|---|
| NV | 11490 | 38.9% |
| EX | 6440 | 21.8% |
| EQ | 3897 | 13.2% |
| TEXT | 3519 | 11.9% |
| MC | 1335 | 4.5% |
| 3-4 parts | 958 | 3.2% |
| NV, NV | 860 | 2.9% |
| EQ, EQ | 359 | 1.2% |
| EX, EX | 270 | 0.9% |
| TF | 208 | 0.7% |
| NV, EX | 52 | 0.2% |
| EX, NV | 34 | 0.1% |
| EQ, EX | 28 | 0.1% |
| EX, EQ | 25 | 0.1% |
| NV, EQ | 13 | 0.0% |
| EQ, NV | 12 | 0.0% |

## Lengths (tokens)

| part | median | p90 | max |
|---|---|---|---|
| prompt | 194 | 267 | 896 |
| think | 476 | 997 | 1600 |
| answer | 73 | 131 | 460 |
| total | 762 | 1280 | 2024 |

The base model's median answer on UGPhysics was 4,096 tokens (the limit). These traces are much shorter on purpose: the model should learn to finish its reasoning.

## Grader check

The worked solution's own boxed answer must agree with the reference answer (official UGPhysics grader).

| result | items |
|---|---|
| agrees | 24700 |
| disagrees | 17272 |
| unchecked (no boxed answer in the solution, or free-form reference) | 5848 |
| agrees after normalising | 2035 |

26735 of 44007 checked items agree (60.8%). The ones that disagree are listed in grader_drops.csv.

## Removed

- resembling an exam question: 1786 of 158342 candidates {'13-word': 872, 'tf-idf': 800, 'exact': 114} (see leak_report.csv)
- while building: {'needs a figure, table or handbook case': 748, 'reference_too_long': 2570, 'no_reference': 23, 'maths proof': 1932, 'math_unboxable': 2680, 'pe_empty': 12, 'duplicate question': 566, 'too long': 24354, 'too short': 37}

## Settings

```
{
 "cmd": "build",
 "workdir": "/content/drive/MyDrive/physics_eval",
 "name": "v1.1",
 "n_total": 30000,
 "n_val": 500,
 "max_tokens": 2048,
 "max_think_tokens": 1600,
 "leak_threshold": 0.4,
 "math_pool": 12000,
 "nemotron_pool": 6000,
 "nr_pool": 100000,
 "neg_pool": 4000,
 "no_natural_reasoning": false,
 "workers": 2,
 "tokenizer": null,
 "megascience_file": null,
 "physicseval_file": null,
 "limit_megascience": 0
}
```
