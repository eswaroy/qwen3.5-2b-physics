# Physics baseline evaluation

Generated 2026-11-19 07:49:58. Every run gets the same questions and prompts.

## Runs

| run | model | chat-template options | max new tokens | repetition penalty | decoding | backend | dtype | GPU | padding-safe |
|---|---|---|---|---|---|---|---|---|---|
| ft-qwen-v1.2-lora-s647-x50 | Qwen/Qwen3.5-2B | {"enable_thinking": false} | 4096 | 1.0 | greedy | hf | float16 | Tesla T4 | True |
| qwen35-2b-nothink | Qwen/Qwen3.5-2B | {"enable_thinking": false} | 4096 | 1.0 | greedy | hf | float16 | Tesla T4 | True |
| cmp-qwen3-1.7b-megascience | MegaScience/Qwen3-1.7B-MegaScience | {} | 4096 | 1.0 | greedy | vllm | float16 | Tesla T4 | n/a |
| cmp-r1-distill-qwen-1.5b | deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B | {} | 8192 | 1.0 | T=0.6, top-p 0.95 | vllm | float16 | Tesla T4 | n/a |
| cmp-openreasoning-nemotron-1.5b | nvidia/OpenReasoning-Nemotron-1.5B | {} | 8192 | 1.0 | T=0.6, top-p 0.95 | vllm | float16 | Tesla T4 | n/a |

**WARNING: these runs do not share the same decoding settings (see the table). Only compare runs with identical settings, or say clearly that they differ.**

## MATH-500 (regression check)

Graded with the same rule judge. Use it to compare runs with each other, not with published MATH-500 numbers, which use a different grader.

| run | items done / planned | accuracy % [95% CI] | unweighted % |
|---|---|---|---|
| ft-qwen-v1.2-lora-s647-x50 | 210 / 210 | 63.5 [56.6, 69.9] | 61.0 |
| qwen35-2b-nothink | 210 / 210 | 73.0 [67.3, 78.7] | 68.6 |
| cmp-qwen3-1.7b-megascience | 210 / 210 | 63.0 [56.5, 69.1] | 59.5 |
| cmp-r1-distill-qwen-1.5b | 210 / 210 | 78.2 [73.0, 83.7] | 74.8 |
| cmp-openreasoning-nemotron-1.5b | 210 / 210 | 54.7 [47.8, 61.4] | 51.4 |

### Accuracy by subject (%)

| subject | items | ft-qwen-v1.2-lora-s647-x50 | qwen35-2b-nothink | cmp-qwen3-1.7b-megascience | cmp-r1-distill-qwen-1.5b | cmp-openreasoning-nemotron-1.5b |
|---|---|---|---|---|---|---|
| Algebra | 30 | 76.7 | 96.7 | 86.7 | 96.7 | 73.3 |
| Counting & Probability | 30 | 56.7 | 56.7 | 56.7 | 63.3 | 40.0 |
| Geometry | 30 | 50.0 | 46.7 | 46.7 | 66.7 | 30.0 |
| Intermediate Algebra | 30 | 56.7 | 60.0 | 46.7 | 66.7 | 33.3 |
| Number Theory | 30 | 63.3 | 80.0 | 70.0 | 90.0 | 76.7 |
| Prealgebra | 30 | 66.7 | 70.0 | 63.3 | 80.0 | 60.0 |
| Precalculus | 30 | 56.7 | 70.0 | 46.7 | 60.0 | 46.7 |

### Accuracy by level (%)

| level | items | ft-qwen-v1.2-lora-s647-x50 | qwen35-2b-nothink | cmp-qwen3-1.7b-megascience | cmp-r1-distill-qwen-1.5b | cmp-openreasoning-nemotron-1.5b |
|---|---|---|---|---|---|---|
| Level 1 | 17 | 88.2 | 70.6 | 88.2 | 94.1 | 64.7 |
| Level 2 | 39 | 76.9 | 84.6 | 79.5 | 82.1 | 69.2 |
| Level 3 | 42 | 78.6 | 71.4 | 66.7 | 83.3 | 64.3 |
| Level 4 | 59 | 61.0 | 72.9 | 62.7 | 76.3 | 45.8 |
| Level 5 | 53 | 26.4 | 49.1 | 26.4 | 54.7 | 30.2 |

## Generation behaviour

`hit token limit` and `stuck in a loop` answers are almost always wrong. `no final answer` means the model never left its thinking section. If these rates differ a lot between runs, the accuracy gap is partly a budget or looping problem, not physics. If a model loops on more than about 5% of questions, also test it under a new run name with `--repetition-penalty 1.05` and treat its better configuration as the score to beat.

| run | benchmark | items | mean new tokens | median | p90 | thinking share % | finished normally % | hit token limit % | stuck in a loop % | no final answer % | no boxed answer % | tokens/s | GPU hours |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ft-qwen-v1.2-lora-s647-x50 | math500 | 210 | 1046 | 548 | 4096 | 0.0 | 85.7 | 12.9 | 1.4 | 0.0 | 17.6 | 60 | 1.02 |
| qwen35-2b-nothink | math500 | 210 | 1830 | 1080 | 4096 | 0.0 | 72.9 | 24.8 | 2.4 | 0.0 | 23.3 | 98 | 1.09 |
| cmp-qwen3-1.7b-megascience | math500 | 210 | 1498 | 818 | 4096 | 0.0 | 81.4 | 17.6 | 1.0 | 0.0 | 16.2 | 197 | 0.44 |
| cmp-r1-distill-qwen-1.5b | math500 | 210 | 3976 | 3058 | 8192 | 91.6 | 82.4 | 17.1 | 0.5 | 16.2 | 17.6 | 371 | 0.63 |
| cmp-openreasoning-nemotron-1.5b | math500 | 210 | 5639 | 6031 | 8192 | 94.7 | 57.1 | 41.9 | 1.0 | 37.6 | 42.9 | 314 | 1.05 |

## Head-to-head

Compared on the items both runs answered. The difference is A minus B with a paired bootstrap 95% interval; it is significant when the interval excludes zero. `p` is the exact McNemar test.

| A | B | benchmark | metric | common items | A | B | A - B [95% CI] | A better on | B better on | p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ft-qwen-v1.2-lora-s647-x50 | qwen35-2b-nothink | math500 | accuracy | 210 | 63.5 | 73.0 | -9.4 [-16.5, -2.6] | 20 | 36 | 0.0440 | B better |
| ft-qwen-v1.2-lora-s647-x50 | cmp-qwen3-1.7b-megascience | math500 | accuracy | 210 | 63.5 | 63.0 | +0.6 [-6.8, 7.3] | 27 | 24 | 0.7798 | no significant difference |
| ft-qwen-v1.2-lora-s647-x50 | cmp-r1-distill-qwen-1.5b | math500 | accuracy | 210 | 63.5 | 78.2 | -14.6 [-21.7, -8.0] | 10 | 39 | 0.0000 | B better |
| ft-qwen-v1.2-lora-s647-x50 | cmp-openreasoning-nemotron-1.5b | math500 | accuracy | 210 | 63.5 | 54.7 | +8.8 [1.9, 16.2] | 39 | 19 | 0.0119 | A better |
| qwen35-2b-nothink | cmp-qwen3-1.7b-megascience | math500 | accuracy | 210 | 73.0 | 63.0 | +10.0 [4.5, 16.2] | 32 | 13 | 0.0066 | A better |
| qwen35-2b-nothink | cmp-r1-distill-qwen-1.5b | math500 | accuracy | 210 | 73.0 | 78.2 | -5.2 [-10.7, 0.3] | 14 | 27 | 0.0596 | no significant difference |
| qwen35-2b-nothink | cmp-openreasoning-nemotron-1.5b | math500 | accuracy | 210 | 73.0 | 54.7 | +18.3 [11.6, 25.0] | 46 | 10 | 0.0000 | A better |
| cmp-qwen3-1.7b-megascience | cmp-r1-distill-qwen-1.5b | math500 | accuracy | 210 | 63.0 | 78.2 | -15.2 [-21.4, -9.1] | 9 | 41 | 0.0000 | B better |
| cmp-qwen3-1.7b-megascience | cmp-openreasoning-nemotron-1.5b | math500 | accuracy | 210 | 63.0 | 54.7 | +8.2 [1.3, 15.3] | 36 | 19 | 0.0300 | A better |
| cmp-r1-distill-qwen-1.5b | cmp-openreasoning-nemotron-1.5b | math500 | accuracy | 210 | 78.2 | 54.7 | +23.5 [16.4, 30.6] | 55 | 6 | 0.0000 | A better |

## Which model is ahead

- **MATH-500 (accuracy):** `cmp-r1-distill-qwen-1.5b` leads with 78.2%. Its lead over `qwen35-2b-nothink` is within the margin of error. It is significantly ahead of `ft-qwen-v1.2-lora-s647-x50`, `cmp-qwen3-1.7b-megascience`, `cmp-openreasoning-nemotron-1.5b`.
