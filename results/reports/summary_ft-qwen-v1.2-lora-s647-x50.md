# Physics baseline evaluation

Generated 2026-10-16 11:39:50. Every run gets the same questions and prompts.

## Runs

| run | model | chat-template options | max new tokens | repetition penalty | dtype | GPU | model commit | padding-safe |
|---|---|---|---|---|---|---|---|---|
| qwen35-2b-nothink | Qwen/Qwen3.5-2B | {"enable_thinking": false} | 4096 | 1.0 | float16 | Tesla T4 |  | True |
| ft-qwen-v1.2-lora-s647 | Qwen/Qwen3.5-2B | {"enable_thinking": false} | 4096 | 1.0 | float16 | Tesla T4 |  | True |
| ft-qwen-v1.2-lora-s647-x50 | Qwen/Qwen3.5-2B | {"enable_thinking": false} | 4096 | 1.0 | float16 | Tesla T4 |  | True |

## UGPhysics (English)

Accuracy is the estimate for the full 5520-problem English set: each subject is weighted by its real size. `rule` = official rule-based judge only (no API). `rule+units` also accepts a correct number that carries a unit inside the box (diagnostic). `MARJ` = official two-stage protocol, rule judge then LLM judge.

| run | items done / planned | rule accuracy % [95% CI] | unweighted % | macro over subjects % | rule+units % | MC/TF/NV only % | MARJ % [95% CI] | grader errors |
|---|---|---|---|---|---|---|---|---|
| qwen35-2b-nothink | 1008 / 1258 INCOMPLETE | 14.5 [11.9, 17.3] | 13.5 | 13.6 | 14.5 | 22.1 | not run | 0 |
| ft-qwen-v1.2-lora-s647 | 1258 / 1258 | 16.5 [14.0, 18.9] | 15.7 | 15.7 | 16.5 | 24.3 | not run | 0 |
| ft-qwen-v1.2-lora-s647-x50 | 1258 / 1258 | 18.3 [15.6, 20.9] | 17.3 | 17.3 | 18.3 | 27.6 | not run | 0 |

### Rule accuracy by subject (%)

| subject | items | qwen35-2b-nothink | ft-qwen-v1.2-lora-s647 | ft-qwen-v1.2-lora-s647-x50 |
|---|---|---|---|---|
| AtomicPhysics | 100 | 22.8 | 24.0 | 31.0 |
| ClassicalElectromagnetism | 100 | 10.1 | 16.0 | 15.0 |
| ClassicalMechanics | 100 | 16.7 | 17.0 | 15.0 |
| Electrodynamics | 100 | 12.3 | 11.0 | 13.0 |
| GeometricalOptics | 58 | 15.5 | 13.8 | 17.2 |
| QuantumMechanics | 100 | 15.0 | 15.0 | 17.0 |
| Relativity | 100 | 10.3 | 13.0 | 10.0 |
| SemiconductorPhysics | 100 | 16.5 | 27.0 | 25.0 |
| Solid-StatePhysics | 100 | 15.2 | 12.0 | 15.0 |
| StatisticalMechanics | 100 | 6.2 | 12.0 | 9.0 |
| TheoreticalMechanics | 100 | 3.8 | 9.0 | 10.0 |
| Thermodynamics | 100 | 13.6 | 10.0 | 19.0 |
| WaveOptics | 100 | 18.4 | 24.0 | 29.0 |

### Rule accuracy by domain (%)

| domain | items | qwen35-2b-nothink | ft-qwen-v1.2-lora-s647 | ft-qwen-v1.2-lora-s647-x50 |
|---|---|---|---|---|
| Electromagnetism | 358 | 13.9 | 16.5 | 18.7 |
| Mechanics and Thermodynamics | 500 | 10.1 | 12.2 | 12.6 |
| Modern Physics | 400 | 17.4 | 19.5 | 22.0 |

### Rule accuracy by reasoning skill (%)

| reasoning skill | items | qwen35-2b-nothink | ft-qwen-v1.2-lora-s647 | ft-qwen-v1.2-lora-s647-x50 |
|---|---|---|---|---|
| Knowledge Recall | 119 | 35.3 | 30.3 | 36.1 |
| Laws Application | 451 | 13.7 | 16.9 | 20.0 |
| Math Derivation | 481 | 8.0 | 11.4 | 9.8 |
| Practical Application | 159 | 14.0 | 14.5 | 18.9 |
| Unlabelled | 48 | 16.2 | 16.7 | 16.7 |

### Rule accuracy by answer type (%)

| answer type | items | qwen35-2b-nothink | ft-qwen-v1.2-lora-s647 | ft-qwen-v1.2-lora-s647-x50 |
|---|---|---|---|---|
| EQ (equation) | 138 | 11.3 | 14.5 | 11.6 |
| EX (expression) | 329 | 7.5 | 11.2 | 10.6 |
| IN (interval) | 18 | 0.0 | 0.0 | 0.0 |
| MC (multiple choice) | 44 | 24.2 | 43.2 | 47.7 |
| NV (number) | 459 | 19.9 | 19.2 | 22.9 |
| TF (true/false) | 33 | 54.5 | 69.7 | 66.7 |
| multiple answers | 237 | 5.5 | 4.6 | 8.0 |

## MATH-500 (regression check)

Graded with the same rule judge. Use it to compare runs with each other, not with published MATH-500 numbers, which use a different grader.

| run | items done / planned | accuracy % [95% CI] | unweighted % |
|---|---|---|---|
| qwen35-2b-nothink | 70 / 210 INCOMPLETE | 67.1 [56.6, 77.0] | 64.3 |
| ft-qwen-v1.2-lora-s647 | 70 / 70 | 51.7 [39.4, 63.7] | 50.0 |
| ft-qwen-v1.2-lora-s647-x50 | 70 / 70 | 69.4 [58.7, 80.2] | 65.7 |

### Accuracy by subject (%)

| subject | items | qwen35-2b-nothink | ft-qwen-v1.2-lora-s647 | ft-qwen-v1.2-lora-s647-x50 |
|---|---|---|---|---|
| Algebra | 10 | 90.0 | 70.0 | 80.0 |
| Counting & Probability | 10 | 30.0 | 40.0 | 30.0 |
| Geometry | 10 | 70.0 | 50.0 | 70.0 |
| Intermediate Algebra | 10 | 50.0 | 30.0 | 70.0 |
| Number Theory | 10 | 80.0 | 70.0 | 70.0 |
| Prealgebra | 10 | 50.0 | 50.0 | 70.0 |
| Precalculus | 10 | 80.0 | 40.0 | 70.0 |

### Accuracy by level (%)

| level | items | qwen35-2b-nothink | ft-qwen-v1.2-lora-s647 | ft-qwen-v1.2-lora-s647-x50 |
|---|---|---|---|---|
| Level 1 | 6 | 100.0 | 100.0 | 100.0 |
| Level 2 | 12 | 75.0 | 75.0 | 75.0 |
| Level 3 | 19 | 63.2 | 47.4 | 78.9 |
| Level 4 | 18 | 66.7 | 50.0 | 61.1 |
| Level 5 | 15 | 40.0 | 13.3 | 33.3 |

## Generation behaviour

`hit token limit` and `stuck in a loop` answers are almost always wrong. `no final answer` means the model never left its thinking section. If these rates differ a lot between runs, the accuracy gap is partly a budget or looping problem, not physics. If a model loops on more than about 5% of questions, also test it under a new run name with `--repetition-penalty 1.05` and treat its better configuration as the score to beat.

| run | benchmark | items | mean new tokens | median | p90 | thinking share % | finished normally % | hit token limit % | stuck in a loop % | no final answer % | no boxed answer % | tokens/s | GPU hours |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen35-2b-nothink | ugphysics | 1008 | 2816 | 4096 | 4096 | 0.1 | 45.2 | 51.9 | 2.9 | 0.0 | 41.8 | 141 | 5.61 |
| qwen35-2b-nothink | math500 | 70 | 1695 | 960 | 4096 | 0.0 | 74.3 | 21.4 | 4.3 | 0.0 | 22.9 | 91 | 0.36 |
| ft-qwen-v1.2-lora-s647 | ugphysics | 1258 | 694 | 560 | 1150 | 0.0 | 97.1 | 2.1 | 0.8 | 0.0 | 2.7 | 82 | 2.95 |
| ft-qwen-v1.2-lora-s647 | math500 | 70 | 589 | 374 | 1126 | 0.0 | 95.7 | 2.9 | 1.4 | 0.0 | 4.3 | 57 | 0.20 |
| ft-qwen-v1.2-lora-s647-x50 | ugphysics | 1258 | 1012 | 710 | 1728 | 0.0 | 91.3 | 7.7 | 1.0 | 0.0 | 8.5 | 67 | 5.29 |
| ft-qwen-v1.2-lora-s647-x50 | math500 | 70 | 947 | 520 | 2625 | 0.0 | 88.6 | 10.0 | 1.4 | 0.0 | 11.4 | 64 | 0.29 |

## Head-to-head

Compared on the items both runs answered. The difference is A minus B with a paired bootstrap 95% interval; it is significant when the interval excludes zero. `p` is the exact McNemar test.

| A | B | benchmark | metric | common items | A | B | A - B [95% CI] | A better on | B better on | p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen35-2b-nothink | ft-qwen-v1.2-lora-s647 | ugphysics | rule accuracy | 1008 | 14.5 | 16.6 | -2.0 [-5.1, 0.8] | 63 | 86 | 0.0711 | no significant difference (item sets differ or incomplete) |
| qwen35-2b-nothink | ft-qwen-v1.2-lora-s647 | ugphysics | rule+units accuracy | 1008 | 14.5 | 16.6 | -2.0 [-5.1, 0.8] | 63 | 86 | 0.0711 | no significant difference (item sets differ or incomplete) |
| qwen35-2b-nothink | ft-qwen-v1.2-lora-s647 | math500 | accuracy | 70 | 67.1 | 51.7 | +15.4 [4.7, 27.0] | 14 | 4 | 0.0309 | A better (item sets differ or incomplete) |
| qwen35-2b-nothink | ft-qwen-v1.2-lora-s647-x50 | ugphysics | rule accuracy | 1008 | 14.5 | 17.9 | -3.3 [-6.4, -0.4] | 51 | 86 | 0.0035 | B better (item sets differ or incomplete) |
| qwen35-2b-nothink | ft-qwen-v1.2-lora-s647-x50 | ugphysics | rule+units accuracy | 1008 | 14.5 | 17.9 | -3.3 [-6.4, -0.4] | 51 | 86 | 0.0035 | B better (item sets differ or incomplete) |
| qwen35-2b-nothink | ft-qwen-v1.2-lora-s647-x50 | math500 | accuracy | 70 | 67.1 | 69.4 | -2.3 [-12.7, 8.4] | 6 | 7 | 1.0000 | no significant difference (item sets differ or incomplete) |
| ft-qwen-v1.2-lora-s647 | ft-qwen-v1.2-lora-s647-x50 | ugphysics | rule accuracy | 1258 | 16.5 | 18.3 | -1.8 [-4.1, 0.4] | 55 | 75 | 0.0953 | no significant difference |
| ft-qwen-v1.2-lora-s647 | ft-qwen-v1.2-lora-s647-x50 | ugphysics | rule+units accuracy | 1258 | 16.5 | 18.3 | -1.8 [-4.1, 0.4] | 55 | 75 | 0.0953 | no significant difference |
| ft-qwen-v1.2-lora-s647 | ft-qwen-v1.2-lora-s647-x50 | math500 | accuracy | 70 | 51.7 | 69.4 | -17.8 [-30.6, -5.3] | 4 | 15 | 0.0192 | B better |

## Which model is ahead

- **UGPhysics (rule accuracy):** `ft-qwen-v1.2-lora-s647-x50` leads with 18.3%. Its lead over `ft-qwen-v1.2-lora-s647` is within the margin of error. It is significantly ahead of `qwen35-2b-nothink`. (Some runs are incomplete, so this is provisional.)
- **MATH-500 (accuracy):** `ft-qwen-v1.2-lora-s647-x50` leads with 69.4%. Its lead over `qwen35-2b-nothink` is within the margin of error. It is significantly ahead of `ft-qwen-v1.2-lora-s647`. (Some runs are incomplete, so this is provisional.)
