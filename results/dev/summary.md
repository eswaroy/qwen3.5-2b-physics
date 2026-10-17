# Physics baseline evaluation

Generated 2026-10-17 07:57:11. Every run gets the same questions and prompts.

## Runs

| run | model | chat-template options | max new tokens | repetition penalty | dtype | GPU | model commit | padding-safe |
|---|---|---|---|---|---|---|---|---|
| lfm25-1.2b-thinking | LiquidAI/LFM2.5-1.2B-Thinking | {} | 4096 | 1.0 | float16 | Tesla T4 |  | True |
| qwen35-2b-nothink | Qwen/Qwen3.5-2B | {"enable_thinking": false} | 4096 | 1.0 | float16 | Tesla T4 |  | True |
| qwen35-2b-think | Qwen/Qwen3.5-2B | {"enable_thinking": true} | 4096 | 1.0 | float16 | Tesla T4 |  | True |
| ft-qwen-v1.2-lora-s647 | Qwen/Qwen3.5-2B | {"enable_thinking": false} | 4096 | 1.0 | float16 | Tesla T4 |  | True |
| ft-qwen-v1.2-lora-s647-x50 | Qwen/Qwen3.5-2B | {"enable_thinking": false} | 4096 | 1.0 | float16 | Tesla T4 |  | True |

## UGPhysics (English)

Accuracy is the estimate for the full 5520-problem English set: each subject is weighted by its real size. `rule` = official rule-based judge only (no API). `rule+units` also accepts a correct number that carries a unit inside the box (diagnostic). `MARJ` = official two-stage protocol, rule judge then LLM judge.

| run | items done / planned | rule accuracy % [95% CI] | unweighted % | macro over subjects % | rule+units % | MC/TF/NV only % | MARJ % [95% CI] | grader errors |
|---|---|---|---|---|---|---|---|---|
| lfm25-1.2b-thinking | 1258 / 1258 | 11.3 [9.1, 13.5] | 10.5 | 10.4 | 11.3 | 16.8 | not run | 1 |
| qwen35-2b-nothink | 1008 / 1258 INCOMPLETE | 14.5 [11.9, 17.3] | 13.5 | 13.6 | 14.5 | 22.1 | not run | 0 |
| qwen35-2b-think | 672 / 1258 INCOMPLETE | 0.0 [0.0, 0.0] | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 [0.0, 0.0] | 0 |
| ft-qwen-v1.2-lora-s647 | 1258 / 1258 | 16.5 [14.0, 18.9] | 15.7 | 15.7 | 16.5 | 24.3 | not run | 0 |
| ft-qwen-v1.2-lora-s647-x50 | 1258 / 1258 | 18.3 [15.6, 20.9] | 17.3 | 17.3 | 18.3 | 27.6 | not run | 0 |

### Rule accuracy by subject (%)

| subject | items | lfm25-1.2b-thinking | qwen35-2b-nothink | qwen35-2b-think | ft-qwen-v1.2-lora-s647 | ft-qwen-v1.2-lora-s647-x50 |
|---|---|---|---|---|---|---|
| AtomicPhysics | 100 | 16.0 | 22.8 | 0.0 | 24.0 | 31.0 |
| ClassicalElectromagnetism | 100 | 11.0 | 10.1 | 0.0 | 16.0 | 15.0 |
| ClassicalMechanics | 100 | 10.0 | 16.7 | 0.0 | 17.0 | 15.0 |
| Electrodynamics | 100 | 2.0 | 12.3 | 0.0 | 11.0 | 13.0 |
| GeometricalOptics | 58 | 6.9 | 15.5 | 0.0 | 13.8 | 17.2 |
| QuantumMechanics | 100 | 13.0 | 15.0 | 0.0 | 15.0 | 17.0 |
| Relativity | 100 | 7.0 | 10.3 | 0.0 | 13.0 | 10.0 |
| SemiconductorPhysics | 100 | 26.0 | 16.5 | 0.0 | 27.0 | 25.0 |
| Solid-StatePhysics | 100 | 10.0 | 15.2 | 0.0 | 12.0 | 15.0 |
| StatisticalMechanics | 100 | 10.0 | 6.2 | 0.0 | 12.0 | 9.0 |
| TheoreticalMechanics | 100 | 3.0 | 3.8 | 0.0 | 9.0 | 10.0 |
| Thermodynamics | 100 | 8.0 | 13.6 | 0.0 | 10.0 | 19.0 |
| WaveOptics | 100 | 12.0 | 18.4 | 0.0 | 24.0 | 29.0 |

### Rule accuracy by domain (%)

| domain | items | lfm25-1.2b-thinking | qwen35-2b-nothink | qwen35-2b-think | ft-qwen-v1.2-lora-s647 | ft-qwen-v1.2-lora-s647-x50 |
|---|---|---|---|---|---|---|
| Electromagnetism | 358 | 8.1 | 13.9 | 0.0 | 16.5 | 18.7 |
| Mechanics and Thermodynamics | 500 | 7.6 | 10.1 | 0.0 | 12.2 | 12.6 |
| Modern Physics | 400 | 16.2 | 17.4 | 0.0 | 19.5 | 22.0 |

### Rule accuracy by reasoning skill (%)

| reasoning skill | items | lfm25-1.2b-thinking | qwen35-2b-nothink | qwen35-2b-think | ft-qwen-v1.2-lora-s647 | ft-qwen-v1.2-lora-s647-x50 |
|---|---|---|---|---|---|---|
| Knowledge Recall | 119 | 30.3 | 35.3 | 0.0 | 30.3 | 36.1 |
| Laws Application | 451 | 9.3 | 13.7 | 0.0 | 16.9 | 20.0 |
| Math Derivation | 481 | 6.7 | 8.0 | 0.0 | 11.4 | 9.8 |
| Practical Application | 159 | 8.8 | 14.0 | 0.0 | 14.5 | 18.9 |
| Unlabelled | 48 | 16.7 | 16.2 | 0.0 | 16.7 | 16.7 |

### Rule accuracy by answer type (%)

| answer type | items | lfm25-1.2b-thinking | qwen35-2b-nothink | qwen35-2b-think | ft-qwen-v1.2-lora-s647 | ft-qwen-v1.2-lora-s647-x50 |
|---|---|---|---|---|---|---|
| EQ (equation) | 138 | 8.7 | 11.3 | 0.0 | 14.5 | 11.6 |
| EX (expression) | 329 | 6.7 | 7.5 | 0.0 | 11.2 | 10.6 |
| IN (interval) | 18 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| MC (multiple choice) | 44 | 40.9 | 24.2 | 0.0 | 43.2 | 47.7 |
| NV (number) | 459 | 12.6 | 19.9 | 0.0 | 19.2 | 22.9 |
| TF (true/false) | 33 | 42.4 | 54.5 | 0.0 | 69.7 | 66.7 |
| multiple answers | 237 | 3.4 | 5.5 | 0.0 | 4.6 | 8.0 |

## PhysicsEval (test split)

Free-text answers, graded only by the LLM judge with the official rubric: six 1-5 scores and an overall correctness score from 0 to 10. Answers with no final text get the minimum.

| run | items done / planned | overall correctness 0-10 [95% CI] | share scoring 8+ % | mathematical accuracy | logical consistency | completeness | clarity and coherence | formulas principles | assumptions made |
|---|---|---|---|---|---|---|---|---|---|
| lfm25-1.2b-thinking | 356 / 356 | needs the judge step (104/356 judged) | - | - | - | - | - | - | - |

## MATH-500 (regression check)

Graded with the same rule judge. Use it to compare runs with each other, not with published MATH-500 numbers, which use a different grader.

| run | items done / planned | accuracy % [95% CI] | unweighted % |
|---|---|---|---|
| lfm25-1.2b-thinking | 210 / 210 | 67.7 [61.4, 73.8] | 63.3 |
| qwen35-2b-nothink | 210 / 210 | 73.0 [67.3, 78.7] | 68.6 |
| ft-qwen-v1.2-lora-s647 | 70 / 70 | 51.7 [39.4, 63.7] | 50.0 |
| ft-qwen-v1.2-lora-s647-x50 | 210 / 210 | 63.5 [56.6, 69.9] | 61.0 |

### Accuracy by subject (%)

| subject | items | lfm25-1.2b-thinking | qwen35-2b-nothink | ft-qwen-v1.2-lora-s647 | ft-qwen-v1.2-lora-s647-x50 |
|---|---|---|---|---|---|
| Algebra | 30 | 86.7 | 96.7 | 70.0 | 76.7 |
| Counting & Probability | 30 | 53.3 | 56.7 | 40.0 | 56.7 |
| Geometry | 30 | 36.7 | 46.7 | 50.0 | 50.0 |
| Intermediate Algebra | 30 | 53.3 | 60.0 | 30.0 | 56.7 |
| Number Theory | 30 | 80.0 | 80.0 | 70.0 | 63.3 |
| Prealgebra | 30 | 76.7 | 70.0 | 50.0 | 66.7 |
| Precalculus | 30 | 56.7 | 70.0 | 40.0 | 56.7 |

### Accuracy by level (%)

| level | items | lfm25-1.2b-thinking | qwen35-2b-nothink | ft-qwen-v1.2-lora-s647 | ft-qwen-v1.2-lora-s647-x50 |
|---|---|---|---|---|---|
| Level 1 | 17 | 88.2 | 70.6 | 100.0 | 88.2 |
| Level 2 | 39 | 84.6 | 84.6 | 75.0 | 76.9 |
| Level 3 | 42 | 64.3 | 71.4 | 47.4 | 78.6 |
| Level 4 | 59 | 67.8 | 72.9 | 50.0 | 61.0 |
| Level 5 | 53 | 34.0 | 49.1 | 13.3 | 26.4 |

## Generation behaviour

`hit token limit` and `stuck in a loop` answers are almost always wrong. `no final answer` means the model never left its thinking section. If these rates differ a lot between runs, the accuracy gap is partly a budget or looping problem, not physics. If a model loops on more than about 5% of questions, also test it under a new run name with `--repetition-penalty 1.05` and treat its better configuration as the score to beat.

| run | benchmark | items | mean new tokens | median | p90 | thinking share % | finished normally % | hit token limit % | stuck in a loop % | no final answer % | no boxed answer % | tokens/s | GPU hours |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lfm25-1.2b-thinking | ugphysics | 1258 | 3658 | 4096 | 4096 | 97.9 | 38.6 | 61.2 | 0.2 | 48.6 | 49.8 | 287 | 4.46 |
| lfm25-1.2b-thinking | physicseval | 356 | 2725 | 2547 | 4096 | 98.4 | 68.3 | 31.5 | 0.3 | 29.2 | - | 217 | 1.24 |
| lfm25-1.2b-thinking | math500 | 210 | 2739 | 2767 | 4096 | 94.7 | 67.6 | 31.9 | 0.5 | 30.5 | 32.4 | 228 | 0.70 |
| qwen35-2b-nothink | ugphysics | 1008 | 2816 | 4096 | 4096 | 0.1 | 45.2 | 51.9 | 2.9 | 0.0 | 41.8 | 141 | 5.61 |
| qwen35-2b-nothink | math500 | 210 | 1830 | 1080 | 4096 | 0.0 | 72.9 | 24.8 | 2.4 | 0.0 | 23.3 | 98 | 1.09 |
| qwen35-2b-think | ugphysics | 672 | 3627 | 4096 | 4096 | 100.0 | 0.0 | 74.4 | 25.6 | 100.0 | 100.0 | 188 | 3.61 |
| ft-qwen-v1.2-lora-s647 | ugphysics | 1258 | 694 | 560 | 1150 | 0.0 | 97.1 | 2.1 | 0.8 | 0.0 | 2.7 | 82 | 2.95 |
| ft-qwen-v1.2-lora-s647 | math500 | 70 | 589 | 374 | 1126 | 0.0 | 95.7 | 2.9 | 1.4 | 0.0 | 4.3 | 57 | 0.20 |
| ft-qwen-v1.2-lora-s647-x50 | ugphysics | 1258 | 1012 | 710 | 1728 | 0.0 | 91.3 | 7.7 | 1.0 | 0.0 | 8.5 | 67 | 5.29 |
| ft-qwen-v1.2-lora-s647-x50 | math500 | 210 | 1046 | 548 | 4096 | 0.0 | 85.7 | 12.9 | 1.4 | 0.0 | 17.6 | 60 | 1.02 |

## Head-to-head

Compared on the items both runs answered. The difference is A minus B with a paired bootstrap 95% interval; it is significant when the interval excludes zero. `p` is the exact McNemar test.

| A | B | benchmark | metric | common items | A | B | A - B [95% CI] | A better on | B better on | p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| lfm25-1.2b-thinking | qwen35-2b-nothink | ugphysics | rule accuracy | 1008 | 11.1 | 14.5 | -3.5 [-6.3, -0.6] | 47 | 82 | 0.0026 | B better (item sets differ or incomplete) |
| lfm25-1.2b-thinking | qwen35-2b-nothink | ugphysics | rule+units accuracy | 1008 | 11.1 | 14.5 | -3.5 [-6.3, -0.6] | 47 | 82 | 0.0026 | B better (item sets differ or incomplete) |
| lfm25-1.2b-thinking | qwen35-2b-nothink | math500 | accuracy | 210 | 67.7 | 73.0 | -5.2 [-11.1, 0.8] | 16 | 27 | 0.1263 | no significant difference |
| lfm25-1.2b-thinking | qwen35-2b-think | ugphysics | rule accuracy | 672 | 12.3 | 0.0 | +12.3 [9.2, 15.4] | 75 | 0 | 0.0000 | A better (item sets differ or incomplete) |
| lfm25-1.2b-thinking | qwen35-2b-think | ugphysics | rule+units accuracy | 672 | 12.3 | 0.0 | +12.3 [9.2, 15.4] | 75 | 0 | 0.0000 | A better (item sets differ or incomplete) |
| lfm25-1.2b-thinking | ft-qwen-v1.2-lora-s647 | ugphysics | rule accuracy | 1258 | 11.3 | 16.5 | -5.1 [-7.5, -2.7] | 51 | 117 | 0.0000 | B better |
| lfm25-1.2b-thinking | ft-qwen-v1.2-lora-s647 | ugphysics | rule+units accuracy | 1258 | 11.3 | 16.5 | -5.1 [-7.5, -2.7] | 51 | 117 | 0.0000 | B better |
| lfm25-1.2b-thinking | ft-qwen-v1.2-lora-s647 | math500 | accuracy | 70 | 67.5 | 51.7 | +15.8 [5.8, 27.3] | 12 | 3 | 0.0352 | A better (item sets differ or incomplete) |
| lfm25-1.2b-thinking | ft-qwen-v1.2-lora-s647-x50 | ugphysics | rule accuracy | 1258 | 11.3 | 18.3 | -6.9 [-9.3, -4.6] | 41 | 127 | 0.0000 | B better |
| lfm25-1.2b-thinking | ft-qwen-v1.2-lora-s647-x50 | ugphysics | rule+units accuracy | 1258 | 11.3 | 18.3 | -6.9 [-9.3, -4.6] | 41 | 127 | 0.0000 | B better |
| lfm25-1.2b-thinking | ft-qwen-v1.2-lora-s647-x50 | math500 | accuracy | 210 | 67.7 | 63.5 | +4.2 [-2.0, 11.0] | 27 | 22 | 0.5682 | no significant difference |
| qwen35-2b-nothink | qwen35-2b-think | ugphysics | rule accuracy | 672 | 16.5 | 0.0 | +16.5 [13.0, 20.0] | 103 | 0 | 0.0000 | A better (item sets differ or incomplete) |
| qwen35-2b-nothink | qwen35-2b-think | ugphysics | rule+units accuracy | 672 | 16.5 | 0.0 | +16.5 [13.0, 20.0] | 103 | 0 | 0.0000 | A better (item sets differ or incomplete) |
| qwen35-2b-nothink | ft-qwen-v1.2-lora-s647 | ugphysics | rule accuracy | 1008 | 14.5 | 16.6 | -2.0 [-5.1, 0.8] | 63 | 86 | 0.0711 | no significant difference (item sets differ or incomplete) |
| qwen35-2b-nothink | ft-qwen-v1.2-lora-s647 | ugphysics | rule+units accuracy | 1008 | 14.5 | 16.6 | -2.0 [-5.1, 0.8] | 63 | 86 | 0.0711 | no significant difference (item sets differ or incomplete) |
| qwen35-2b-nothink | ft-qwen-v1.2-lora-s647 | math500 | accuracy | 70 | 67.1 | 51.7 | +15.4 [4.7, 27.0] | 14 | 4 | 0.0309 | A better (item sets differ or incomplete) |
| qwen35-2b-nothink | ft-qwen-v1.2-lora-s647-x50 | ugphysics | rule accuracy | 1008 | 14.5 | 17.9 | -3.3 [-6.4, -0.4] | 51 | 86 | 0.0035 | B better (item sets differ or incomplete) |
| qwen35-2b-nothink | ft-qwen-v1.2-lora-s647-x50 | ugphysics | rule+units accuracy | 1008 | 14.5 | 17.9 | -3.3 [-6.4, -0.4] | 51 | 86 | 0.0035 | B better (item sets differ or incomplete) |
| qwen35-2b-nothink | ft-qwen-v1.2-lora-s647-x50 | math500 | accuracy | 210 | 73.0 | 63.5 | +9.4 [2.6, 16.5] | 36 | 20 | 0.0440 | A better |
| qwen35-2b-think | ft-qwen-v1.2-lora-s647 | ugphysics | rule accuracy | 672 | 0.0 | 16.8 | -16.8 [-20.1, -13.3] | 0 | 108 | 0.0000 | B better (item sets differ or incomplete) |
| qwen35-2b-think | ft-qwen-v1.2-lora-s647 | ugphysics | rule+units accuracy | 672 | 0.0 | 16.8 | -16.8 [-20.1, -13.3] | 0 | 108 | 0.0000 | B better (item sets differ or incomplete) |
| qwen35-2b-think | ft-qwen-v1.2-lora-s647-x50 | ugphysics | rule accuracy | 672 | 0.0 | 17.6 | -17.6 [-21.2, -14.1] | 0 | 113 | 0.0000 | B better (item sets differ or incomplete) |
| qwen35-2b-think | ft-qwen-v1.2-lora-s647-x50 | ugphysics | rule+units accuracy | 672 | 0.0 | 17.6 | -17.6 [-21.2, -14.1] | 0 | 113 | 0.0000 | B better (item sets differ or incomplete) |
| ft-qwen-v1.2-lora-s647 | ft-qwen-v1.2-lora-s647-x50 | ugphysics | rule accuracy | 1258 | 16.5 | 18.3 | -1.8 [-4.1, 0.4] | 55 | 75 | 0.0953 | no significant difference |
| ft-qwen-v1.2-lora-s647 | ft-qwen-v1.2-lora-s647-x50 | ugphysics | rule+units accuracy | 1258 | 16.5 | 18.3 | -1.8 [-4.1, 0.4] | 55 | 75 | 0.0953 | no significant difference |
| ft-qwen-v1.2-lora-s647 | ft-qwen-v1.2-lora-s647-x50 | math500 | accuracy | 70 | 51.7 | 69.4 | -17.8 [-30.6, -5.3] | 4 | 15 | 0.0192 | B better (item sets differ or incomplete) |

## Which model is ahead

- **UGPhysics (rule accuracy):** `ft-qwen-v1.2-lora-s647-x50` leads with 18.3%. Its lead over `ft-qwen-v1.2-lora-s647` is within the margin of error. It is significantly ahead of `qwen35-2b-nothink`, `lfm25-1.2b-thinking`, `qwen35-2b-think`. (Some runs are incomplete, so this is provisional.)
- **MATH-500 (accuracy):** `qwen35-2b-nothink` leads with 73.0%. Its lead over `lfm25-1.2b-thinking` is within the margin of error. It is significantly ahead of `ft-qwen-v1.2-lora-s647-x50`, `ft-qwen-v1.2-lora-s647`. (Some runs are incomplete, so this is provisional.)
