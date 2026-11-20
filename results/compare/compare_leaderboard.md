# Physics comparison: about 2B open models

UGPhysics (English) held-out test: 1,142 questions (ranks 100-199 in 12 subjects), official prompt and rule judge, accuracy weighted by subject. MATH-500: 210 problems. 95% intervals in brackets. 'Ours minus model' and wins/losses are paired on the same questions (exact McNemar p).

| Model | Decoding | UGPhysics held-out % | Ours minus model | Ours wins / losses | p | MATH-500 % |
|---|---|---|---|---|---|---|
| **This model** (Qwen3.5-2B + half-strength LoRA) | greedy, 4096 tok | 18.9 [16.3, 21.7] | - | - | - | 63.5 [56.6, 69.9] |
| Qwen3.5-2B, non-thinking (base) | greedy, 4096 tok | 15.9 [13.6, 18.5] | +3.0 [+0.3, +5.7] | 102 / 75 | 0.0504 | 73.0 [67.3, 78.7] |
| MegaScience/Qwen3-1.7B-MegaScience | greedy, 4096 tok | 12.6 [10.5, 15.0] | +6.3 [+3.7, +8.9] | 118 / 46 | 0.0000 | 63.0 [56.5, 69.1] |
| deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B | T 0.6, 8192 tok | 9.8 [7.8, 11.9] | +9.1 [+6.4, +11.8] | 143 / 39 | 0.0000 | 78.2 [73.0, 83.7] |
| nvidia/OpenReasoning-Nemotron-1.5B | T 0.6, 8192 tok | 5.0 [3.5, 6.5] | +13.9 [+11.3, +16.6] | 174 / 19 | 0.0000 | 54.7 [47.8, 61.4] |
