# Training data v1.2

Built 2026-10-08 16:58:43 with physdata.py 1.2. 29500 training and 500 validation examples.

Token counts are exact (LFM2.5 tokenizer).

## Mix

| style | items | share |
|---|---|---|
| ug | 21214 | 71.9% |
| plain | 3541 | 12.0% |
| math | 2943 | 10.0% |
| knowledge | 1481 | 5.0% |
| pe | 321 | 1.1% |

## Source

| source | items | share |
|---|---|---|
| megascience_physics | 17548 | 59.5% |
| naturalreasoning_physics | 7390 | 25.1% |
| megascience_math | 2943 | 10.0% |
| nemotron_physics | 1298 | 4.4% |
| physicseval_train | 321 | 1.1% |

## Subjects of the physics examples vs the exam

Target = exam share x weakness (weakness weights from the lfm25-1.2b-thinking baseline (weaker subject = more examples)), at least 2%. Tagged by the classifier.

| subject | exam share | target | items | share of physics items | base accuracy |
|---|---|---|---|---|---|
| QuantumMechanics | 18.5% | 16.4% | 2664 | 10.0% | 13.0% |
| AtomicPhysics | 16.6% | 12.7% | 1692 | 6.4% | 16.0% |
| ClassicalMechanics | 15.1% | 15.7% | 6179 | 23.3% | 10.0% |
| StatisticalMechanics | 10.1% | 10.5% | 1436 | 5.4% | 10.0% |
| ClassicalElectromagnetism | 7.1% | 7.0% | 2866 | 10.8% | 11.0% |
| Thermodynamics | 6.7% | 7.6% | 3147 | 11.8% | 8.0% |
| TheoreticalMechanics | 5.8% | 8.0% | 1645 | 6.2% | 3.0% |
| WaveOptics | 5.5% | 5.1% | 1592 | 6.0% | 12.0% |
| Relativity | 3.8% | 4.4% | 1817 | 6.8% | 7.0% |
| SemiconductorPhysics | 3.4% | 2.6% | 549 | 2.1% | 26.0% |
| Electrodynamics | 3.3% | 4.8% | 1890 | 7.1% | 2.0% |
| Solid-StatePhysics | 3.1% | 3.2% | 914 | 3.4% | 10.0% |
| GeometricalOptics | 1.1% | 2.0% | 166 | 0.6% | 6.9% |

Where each subject's examples are lost (physics styles). A subject below its target ran out of examples that pass every step.

| subject | candidates | not like an exam question | length ok | chosen | grader agrees |
|---|---|---|---|---|---|
| QuantumMechanics | 14829 | 14401 | 12059 | 2664 | 59% of 3405 |
| AtomicPhysics | 6568 | 6440 | 5510 | 1692 | 71% of 1752 |
| ClassicalMechanics | 29112 | 28716 | 22820 | 6179 | 55% of 10422 |
| StatisticalMechanics | 7993 | 7924 | 7250 | 1436 | 56% of 1852 |
| ClassicalElectromagnetism | 14281 | 14136 | 11699 | 2866 | 56% of 4648 |
| Thermodynamics | 23355 | 23014 | 19364 | 3147 | 72% of 4057 |
| TheoreticalMechanics | 7898 | 7733 | 6207 | 1645 | 54% of 2481 |
| WaveOptics | 7467 | 7382 | 6354 | 1592 | 68% of 2045 |
| Relativity | 18376 | 18243 | 15641 | 1817 | 50% of 3260 |
| SemiconductorPhysics | 3650 | 3567 | 3251 | 549 | 64% of 680 |
| Electrodynamics | 12756 | 12624 | 10751 | 1890 | 54% of 3083 |
| Solid-StatePhysics | 3846 | 3788 | 3334 | 914 | 71% of 1101 |
| GeometricalOptics | 328 | 310 | 251 | 166 | 76% of 134 |

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
| NV | 11385 | 38.6% |
| EX | 6367 | 21.6% |
| EQ | 4026 | 13.6% |
| TEXT | 3522 | 11.9% |
| MC | 1345 | 4.6% |
| 3-4 parts | 1004 | 3.4% |
| NV, NV | 851 | 2.9% |
| EQ, EQ | 346 | 1.2% |
| EX, EX | 276 | 0.9% |
| TF | 212 | 0.7% |
| NV, EX | 62 | 0.2% |
| EX, NV | 33 | 0.1% |
| EQ, EX | 26 | 0.1% |
| EX, EQ | 25 | 0.1% |
| NV, EQ | 11 | 0.0% |
| EQ, NV | 9 | 0.0% |

## Lengths (tokens)

| part | median | p90 | max |
|---|---|---|---|
| prompt | 194 | 266 | 1404 |
| think | 479 | 987 | 1600 |
| answer | 71 | 131 | 397 |
| total | 763 | 1275 | 2021 |

The base model's median answer on UGPhysics was 4,096 tokens (the limit). These traces are much shorter on purpose: the model should learn to finish its reasoning.

## Grader check

The worked solution's own boxed answer must agree with the reference answer (official UGPhysics grader).

| result | items |
|---|---|
| disagrees | 16535 |
| agrees | 15999 |
| agrees after normalising | 10636 |
| unchecked (no boxed answer in the solution, or free-form reference) | 5859 |

26635 of 43170 checked items agree (61.7%). The ones that disagree are listed in grader_drops.csv.

## Removed

- resembling an exam question: 1781 of 157777 candidates {'13-word': 845, 'tf-idf': 792, 'numbers': 34, 'exact': 110} (see leak_report.csv)
- while building: {'needs a figure, table or handbook case': 1305, 'reference_too_long': 2570, 'no_reference': 23, 'maths proof': 1932, 'math_unboxable': 2688, 'pe_empty': 12, 'duplicate question': 551, 'too long': 23843, 'too short': 47}

## Settings

```
{
 "cmd": "build",
 "workdir": "/content/drive/MyDrive/physics_eval",
 "name": "v1.2",
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
