# Physics baseline evaluation

Generated 2026-10-17 07:57:07. Every run gets the same questions and prompts.

## Runs

| run | model | chat-template options | max new tokens | repetition penalty | dtype | GPU | model commit | padding-safe |
|---|---|---|---|---|---|---|---|---|
| qwen35-2b-nothink-test | Qwen/Qwen3.5-2B | {"enable_thinking": false} | 4096 | 1.0 | float16 | Tesla T4 |  | True |
| ft-qwen-v1.2-lora-s647-x50-test | Qwen/Qwen3.5-2B | {"enable_thinking": false} | 4096 | 1.0 | float16 | Tesla T4 |  | True |

## UGPhysics (English)

Accuracy is the estimate for the full 5520-problem English set: each subject is weighted by its real size. `rule` = official rule-based judge only (no API). `rule+units` also accepts a correct number that carries a unit inside the box (diagnostic). `MARJ` = official two-stage protocol, rule judge then LLM judge.

| run | items done / planned | rule accuracy % [95% CI] | unweighted % | macro over subjects % | rule+units % | MC/TF/NV only % | MARJ % [95% CI] | grader errors |
|---|---|---|---|---|---|---|---|---|
| qwen35-2b-nothink-test | 1142 / 1142 | 15.9 [13.6, 18.5] | 15.7 | 15.6 | 15.9 | 27.5 | not run | 0 |
| ft-qwen-v1.2-lora-s647-x50-test | 1142 / 1142 | 18.9 [16.3, 21.7] | 18.0 | 18.0 | 18.9 | 31.3 | not run | 0 |

### Rule accuracy by subject (%)

| subject | items | qwen35-2b-nothink-test | ft-qwen-v1.2-lora-s647-x50-test |
|---|---|---|---|
| AtomicPhysics | 100 | 27.0 | 26.0 |
| ClassicalElectromagnetism | 100 | 16.0 | 15.0 |
| ClassicalMechanics | 100 | 16.0 | 26.0 |
| Electrodynamics | 84 | 10.7 | 17.9 |
| QuantumMechanics | 100 | 11.0 | 18.0 |
| Relativity | 100 | 21.0 | 20.0 |
| SemiconductorPhysics | 86 | 23.3 | 31.4 |
| Solid-StatePhysics | 72 | 11.1 | 11.1 |
| StatisticalMechanics | 100 | 8.0 | 6.0 |
| TheoreticalMechanics | 100 | 8.0 | 12.0 |
| Thermodynamics | 100 | 19.0 | 20.0 |
| WaveOptics | 100 | 16.0 | 13.0 |

### Rule accuracy by domain (%)

| domain | items | qwen35-2b-nothink-test | ft-qwen-v1.2-lora-s647-x50-test |
|---|---|---|---|
| Electromagnetism | 284 | 14.4 | 15.1 |
| Mechanics and Thermodynamics | 500 | 14.4 | 16.8 |
| Modern Physics | 358 | 18.4 | 22.1 |

### Rule accuracy by reasoning skill (%)

| reasoning skill | items | qwen35-2b-nothink-test | ft-qwen-v1.2-lora-s647-x50-test |
|---|---|---|---|
| Knowledge Recall | 105 | 32.4 | 41.9 |
| Laws Application | 412 | 20.9 | 21.6 |
| Math Derivation | 468 | 6.8 | 9.4 |
| Practical Application | 117 | 18.8 | 20.5 |
| Unlabelled | 40 | 12.5 | 12.5 |

### Rule accuracy by answer type (%)

| answer type | items | qwen35-2b-nothink-test | ft-qwen-v1.2-lora-s647-x50-test |
|---|---|---|---|
| EQ (equation) | 148 | 9.5 | 18.2 |
| EX
``` | 1 | 0.0 | 0.0 |
| EX (expression) | 304 | 7.6 | 6.6 |
| IN (interval) | 12 | 8.3 | 0.0 |
| MC (multiple choice) | 35 | 25.7 | 68.6 |
| NV (number) | 384 | 24.2 | 25.8 |
| TF (true/false) | 32 | 68.8 | 56.2 |
| \
MC | 2 | 50.0 | 100.0 |
| multiple answers | 224 | 7.1 | 7.1 |

## Generation behaviour

`hit token limit` and `stuck in a loop` answers are almost always wrong. `no final answer` means the model never left its thinking section. If these rates differ a lot between runs, the accuracy gap is partly a budget or looping problem, not physics. If a model loops on more than about 5% of questions, also test it under a new run name with `--repetition-penalty 1.05` and treat its better configuration as the score to beat.

| run | benchmark | items | mean new tokens | median | p90 | thinking share % | finished normally % | hit token limit % | stuck in a loop % | no final answer % | no boxed answer % | tokens/s | GPU hours |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen35-2b-nothink-test | ugphysics | 1142 | 2720 | 3862 | 4096 | 0.0 | 48.9 | 48.9 | 2.1 | 0.0 | 38.5 | 137 | 6.31 |
| ft-qwen-v1.2-lora-s647-x50-test | ugphysics | 1142 | 1006 | 726 | 1782 | 0.0 | 91.7 | 6.9 | 1.4 | 0.0 | 8.1 | 68 | 4.71 |

## Head-to-head

Compared on the items both runs answered. The difference is A minus B with a paired bootstrap 95% interval; it is significant when the interval excludes zero. `p` is the exact McNemar test.

| A | B | benchmark | metric | common items | A | B | A - B [95% CI] | A better on | B better on | p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen35-2b-nothink-test | ft-qwen-v1.2-lora-s647-x50-test | ugphysics | rule accuracy | 1142 | 15.9 | 18.9 | -3.0 [-5.7, -0.3] | 75 | 102 | 0.0504 | B better |
| qwen35-2b-nothink-test | ft-qwen-v1.2-lora-s647-x50-test | ugphysics | rule+units accuracy | 1142 | 15.9 | 18.9 | -3.0 [-5.7, -0.3] | 75 | 102 | 0.0504 | B better |

## Which model is ahead

- **UGPhysics (rule accuracy):** `ft-qwen-v1.2-lora-s647-x50-test` leads with 18.9%. It is significantly ahead of `qwen35-2b-nothink-test`.
