# Physics baseline evaluation

Generated 2026-11-19 07:49:53. Every run gets the same questions and prompts.

## Runs

| run | model | chat-template options | max new tokens | repetition penalty | decoding | backend | dtype | GPU | padding-safe |
|---|---|---|---|---|---|---|---|---|---|
| ft-qwen-v1.2-lora-s647-x50-test | Qwen/Qwen3.5-2B | {"enable_thinking": false} | 4096 | 1.0 | greedy | hf | float16 | Tesla T4 | True |
| qwen35-2b-nothink-test | Qwen/Qwen3.5-2B | {"enable_thinking": false} | 4096 | 1.0 | greedy | hf | float16 | Tesla T4 | True |
| cmp-qwen3-1.7b-megascience | MegaScience/Qwen3-1.7B-MegaScience | {} | 4096 | 1.0 | greedy | vllm | float16 | Tesla T4 | n/a |
| cmp-r1-distill-qwen-1.5b | deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B | {} | 8192 | 1.0 | T=0.6, top-p 0.95 | vllm | float16 | Tesla T4 | n/a |
| cmp-openreasoning-nemotron-1.5b | nvidia/OpenReasoning-Nemotron-1.5B | {} | 8192 | 1.0 | T=0.6, top-p 0.95 | vllm | float16 | Tesla T4 | n/a |

**WARNING: these runs do not share the same decoding settings (see the table). Only compare runs with identical settings, or say clearly that they differ.**

## UGPhysics (English)

Accuracy is the estimate for the full 5520-problem English set: each subject is weighted by its real size. `rule` = official rule-based judge only (no API). `rule+units` also accepts a correct number that carries a unit inside the box (diagnostic). `MARJ` = official two-stage protocol, rule judge then LLM judge.

| run | items done / planned | rule accuracy % [95% CI] | unweighted % | macro over subjects % | rule+units % | MC/TF/NV only % | MARJ % [95% CI] | grader errors |
|---|---|---|---|---|---|---|---|---|
| ft-qwen-v1.2-lora-s647-x50-test | 1142 / 1142 | 18.9 [16.3, 21.7] | 18.0 | 18.0 | 18.9 | 31.3 | not run | 0 |
| qwen35-2b-nothink-test | 1142 / 1142 | 15.9 [13.6, 18.5] | 15.7 | 15.6 | 15.9 | 27.5 | not run | 0 |
| cmp-qwen3-1.7b-megascience | 1142 / 1142 | 12.6 [10.5, 15.0] | 11.7 | 11.8 | 13.8 | 21.1 | not run | 0 |
| cmp-r1-distill-qwen-1.5b | 1142 / 1142 | 9.8 [7.8, 11.9] | 8.9 | 8.9 | 10.1 | 16.9 | not run | 0 |
| cmp-openreasoning-nemotron-1.5b | 1142 / 1142 | 5.0 [3.5, 6.5] | 4.5 | 4.5 | 5.0 | 6.7 | not run | 0 |

### Rule accuracy by subject (%)

| subject | items | ft-qwen-v1.2-lora-s647-x50-test | qwen35-2b-nothink-test | cmp-qwen3-1.7b-megascience | cmp-r1-distill-qwen-1.5b | cmp-openreasoning-nemotron-1.5b |
|---|---|---|---|---|---|---|
| AtomicPhysics | 100 | 26.0 | 27.0 | 20.0 | 10.0 | 10.0 |
| ClassicalElectromagnetism | 100 | 15.0 | 16.0 | 10.0 | 7.0 | 3.0 |
| ClassicalMechanics | 100 | 26.0 | 16.0 | 11.0 | 18.0 | 6.0 |
| Electrodynamics | 84 | 17.9 | 10.7 | 9.5 | 7.1 | 4.8 |
| QuantumMechanics | 100 | 18.0 | 11.0 | 14.0 | 10.0 | 3.0 |
| Relativity | 100 | 20.0 | 21.0 | 3.0 | 7.0 | 1.0 |
| SemiconductorPhysics | 86 | 31.4 | 23.3 | 24.4 | 11.6 | 5.8 |
| Solid-StatePhysics | 72 | 11.1 | 11.1 | 8.3 | 5.6 | 4.2 |
| StatisticalMechanics | 100 | 6.0 | 8.0 | 6.0 | 4.0 | 3.0 |
| TheoreticalMechanics | 100 | 12.0 | 8.0 | 10.0 | 5.0 | 1.0 |
| Thermodynamics | 100 | 20.0 | 19.0 | 11.0 | 8.0 | 7.0 |
| WaveOptics | 100 | 13.0 | 16.0 | 14.0 | 13.0 | 5.0 |

### Rule accuracy by domain (%)

| domain | items | ft-qwen-v1.2-lora-s647-x50-test | qwen35-2b-nothink-test | cmp-qwen3-1.7b-megascience | cmp-r1-distill-qwen-1.5b | cmp-openreasoning-nemotron-1.5b |
|---|---|---|---|---|---|---|
| Electromagnetism | 284 | 15.1 | 14.4 | 11.3 | 9.2 | 4.2 |
| Mechanics and Thermodynamics | 500 | 16.8 | 14.4 | 8.2 | 8.4 | 3.6 |
| Modern Physics | 358 | 22.1 | 18.4 | 17.0 | 9.5 | 5.9 |

### Rule accuracy by reasoning skill (%)

| reasoning skill | items | ft-qwen-v1.2-lora-s647-x50-test | qwen35-2b-nothink-test | cmp-qwen3-1.7b-megascience | cmp-r1-distill-qwen-1.5b | cmp-openreasoning-nemotron-1.5b |
|---|---|---|---|---|---|---|
| Knowledge Recall | 105 | 41.9 | 32.4 | 34.3 | 20.0 | 19.0 |
| Laws Application | 412 | 21.6 | 20.9 | 14.1 | 12.4 | 5.1 |
| Math Derivation | 468 | 9.4 | 6.8 | 5.3 | 3.8 | 1.7 |
| Practical Application | 117 | 20.5 | 18.8 | 6.8 | 6.8 | 0.0 |
| Unlabelled | 40 | 12.5 | 12.5 | 17.5 | 10.0 | 5.0 |

### Rule accuracy by answer type (%)

| answer type | items | ft-qwen-v1.2-lora-s647-x50-test | qwen35-2b-nothink-test | cmp-qwen3-1.7b-megascience | cmp-r1-distill-qwen-1.5b | cmp-openreasoning-nemotron-1.5b |
|---|---|---|---|---|---|---|
| EQ (equation) | 148 | 18.2 | 9.5 | 15.5 | 8.1 | 4.7 |
| EX
``` | 1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| EX (expression) | 304 | 6.6 | 7.6 | 3.9 | 3.0 | 3.0 |
| IN (interval) | 12 | 0.0 | 8.3 | 0.0 | 0.0 | 8.3 |
| MC (multiple choice) | 35 | 68.6 | 25.7 | 57.1 | 8.6 | 25.7 |
| NV (number) | 384 | 25.8 | 24.2 | 15.9 | 16.1 | 4.2 |
| TF (true/false) | 32 | 56.2 | 68.8 | 43.8 | 34.4 | 15.6 |
| \
MC | 2 | 100.0 | 50.0 | 50.0 | 0.0 | 50.0 |
| multiple answers | 224 | 7.1 | 7.1 | 1.3 | 2.2 | 1.3 |

## Generation behaviour

`hit token limit` and `stuck in a loop` answers are almost always wrong. `no final answer` means the model never left its thinking section. If these rates differ a lot between runs, the accuracy gap is partly a budget or looping problem, not physics. If a model loops on more than about 5% of questions, also test it under a new run name with `--repetition-penalty 1.05` and treat its better configuration as the score to beat.

| run | benchmark | items | mean new tokens | median | p90 | thinking share % | finished normally % | hit token limit % | stuck in a loop % | no final answer % | no boxed answer % | tokens/s | GPU hours |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ft-qwen-v1.2-lora-s647-x50-test | ugphysics | 1142 | 1006 | 726 | 1782 | 0.0 | 91.7 | 6.9 | 1.4 | 0.0 | 8.1 | 68 | 4.71 |
| qwen35-2b-nothink-test | ugphysics | 1142 | 2720 | 3862 | 4096 | 0.0 | 48.9 | 48.9 | 2.1 | 0.0 | 38.5 | 137 | 6.31 |
| cmp-qwen3-1.7b-megascience | ugphysics | 1142 | 1515 | 986 | 4096 | 0.0 | 86.0 | 13.6 | 0.4 | 0.4 | 11.9 | 205 | 2.34 |
| cmp-r1-distill-qwen-1.5b | ugphysics | 1142 | 6460 | 8192 | 8192 | 97.2 | 47.4 | 52.4 | 0.3 | 50.2 | 55.6 | 285 | 7.20 |
| cmp-openreasoning-nemotron-1.5b | ugphysics | 1142 | 7762 | 8192 | 8192 | 99.1 | 15.7 | 83.5 | 0.8 | 82.8 | 84.2 | 269 | 9.16 |

## Head-to-head

Compared on the items both runs answered. The difference is A minus B with a paired bootstrap 95% interval; it is significant when the interval excludes zero. `p` is the exact McNemar test.

| A | B | benchmark | metric | common items | A | B | A - B [95% CI] | A better on | B better on | p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ft-qwen-v1.2-lora-s647-x50-test | qwen35-2b-nothink-test | ugphysics | rule accuracy | 1142 | 18.9 | 15.9 | +3.0 [0.3, 5.7] | 102 | 75 | 0.0504 | A better |
| ft-qwen-v1.2-lora-s647-x50-test | qwen35-2b-nothink-test | ugphysics | rule+units accuracy | 1142 | 18.9 | 15.9 | +3.0 [0.3, 5.7] | 102 | 75 | 0.0504 | A better |
| ft-qwen-v1.2-lora-s647-x50-test | cmp-qwen3-1.7b-megascience | ugphysics | rule accuracy | 1142 | 18.9 | 12.6 | +6.3 [3.7, 8.9] | 118 | 46 | 0.0000 | A better |
| ft-qwen-v1.2-lora-s647-x50-test | cmp-qwen3-1.7b-megascience | ugphysics | rule+units accuracy | 1142 | 18.9 | 13.8 | +5.1 [2.4, 7.6] | 107 | 54 | 0.0000 | A better |
| ft-qwen-v1.2-lora-s647-x50-test | cmp-r1-distill-qwen-1.5b | ugphysics | rule accuracy | 1142 | 18.9 | 9.8 | +9.1 [6.4, 11.8] | 143 | 39 | 0.0000 | A better |
| ft-qwen-v1.2-lora-s647-x50-test | cmp-r1-distill-qwen-1.5b | ugphysics | rule+units accuracy | 1142 | 18.9 | 10.1 | +8.9 [6.1, 11.6] | 142 | 40 | 0.0000 | A better |
| ft-qwen-v1.2-lora-s647-x50-test | cmp-openreasoning-nemotron-1.5b | ugphysics | rule accuracy | 1142 | 18.9 | 5.0 | +13.9 [11.3, 16.6] | 174 | 19 | 0.0000 | A better |
| ft-qwen-v1.2-lora-s647-x50-test | cmp-openreasoning-nemotron-1.5b | ugphysics | rule+units accuracy | 1142 | 18.9 | 5.0 | +13.9 [11.3, 16.6] | 174 | 19 | 0.0000 | A better |
| qwen35-2b-nothink-test | cmp-qwen3-1.7b-megascience | ugphysics | rule accuracy | 1142 | 15.9 | 12.6 | +3.3 [0.5, 6.0] | 112 | 67 | 0.0010 | A better |
| qwen35-2b-nothink-test | cmp-qwen3-1.7b-megascience | ugphysics | rule+units accuracy | 1142 | 15.9 | 13.8 | +2.1 [-0.6, 4.7] | 102 | 76 | 0.0606 | no significant difference |
| qwen35-2b-nothink-test | cmp-r1-distill-qwen-1.5b | ugphysics | rule accuracy | 1142 | 15.9 | 9.8 | +6.1 [3.7, 8.6] | 121 | 44 | 0.0000 | A better |
| qwen35-2b-nothink-test | cmp-r1-distill-qwen-1.5b | ugphysics | rule+units accuracy | 1142 | 15.9 | 10.1 | +5.9 [3.5, 8.4] | 121 | 46 | 0.0000 | A better |
| qwen35-2b-nothink-test | cmp-openreasoning-nemotron-1.5b | ugphysics | rule accuracy | 1142 | 15.9 | 5.0 | +10.9 [8.5, 13.4] | 150 | 22 | 0.0000 | A better |
| qwen35-2b-nothink-test | cmp-openreasoning-nemotron-1.5b | ugphysics | rule+units accuracy | 1142 | 15.9 | 5.0 | +10.9 [8.5, 13.4] | 150 | 22 | 0.0000 | A better |
| cmp-qwen3-1.7b-megascience | cmp-r1-distill-qwen-1.5b | ugphysics | rule accuracy | 1142 | 12.6 | 9.8 | +2.8 [0.5, 5.2] | 86 | 54 | 0.0086 | A better |
| cmp-qwen3-1.7b-megascience | cmp-r1-distill-qwen-1.5b | ugphysics | rule+units accuracy | 1142 | 13.8 | 10.1 | +3.8 [1.4, 6.2] | 99 | 50 | 0.0001 | A better |
| cmp-qwen3-1.7b-megascience | cmp-openreasoning-nemotron-1.5b | ugphysics | rule accuracy | 1142 | 12.6 | 5.0 | +7.6 [5.5, 9.9] | 105 | 22 | 0.0000 | A better |
| cmp-qwen3-1.7b-megascience | cmp-openreasoning-nemotron-1.5b | ugphysics | rule+units accuracy | 1142 | 13.8 | 5.0 | +8.8 [6.7, 11.3] | 124 | 22 | 0.0000 | A better |
| cmp-r1-distill-qwen-1.5b | cmp-openreasoning-nemotron-1.5b | ugphysics | rule accuracy | 1142 | 9.8 | 5.0 | +4.8 [2.9, 6.9] | 83 | 32 | 0.0000 | A better |
| cmp-r1-distill-qwen-1.5b | cmp-openreasoning-nemotron-1.5b | ugphysics | rule+units accuracy | 1142 | 10.1 | 5.0 | +5.1 [3.0, 7.1] | 85 | 32 | 0.0000 | A better |

## Which model is ahead

- **UGPhysics (rule accuracy):** `ft-qwen-v1.2-lora-s647-x50-test` leads with 18.9%. It is significantly ahead of `qwen35-2b-nothink-test`, `cmp-qwen3-1.7b-megascience`, `cmp-r1-distill-qwen-1.5b`, `cmp-openreasoning-nemotron-1.5b`.
