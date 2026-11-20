# Comparison with other small open models

Made by [`notebooks/PhysicsCompare.ipynb`](../../notebooks/PhysicsCompare.ipynb) with [`src/physeval.py`](../../src/physeval.py) 1.5. A readable summary is in [docs/RESULTS.md](../../docs/RESULTS.md#comparison-with-other-small-open-models).

| File | Content |
|---|---|
| `compare_leaderboard.md` | one table: every model's accuracy, its gap to this model (paired interval, wins/losses, McNemar p) and MATH-500 |
| `summary_compare_ugphysics.md` | full report on the 1,142 held-out UGPhysics questions: by subject, domain, reasoning skill, answer type, answer lengths, all pairwise tests |
| `summary_compare_math500.md` | the same for the 210 MATH-500 problems |
| `summary_compare_*.json` | every number of the two reports in machine-readable form |

Every generated and graded answer is in [`../runs/`](../runs) under the run names below.

| Run | Model | Decoding | Engine |
|---|---|---|---|
| `ft-qwen-v1.2-lora-s647-x50-test` / `ft-qwen-v1.2-lora-s647-x50` | this model (UGPhysics test / MATH-500) | greedy, 4,096 tokens | transformers |
| `qwen35-2b-nothink-test` / `qwen35-2b-nothink` | Qwen/Qwen3.5-2B, non-thinking | greedy, 4,096 tokens | transformers |
| `cmp-qwen3-1.7b-megascience` | MegaScience/Qwen3-1.7B-MegaScience | greedy, 4,096 tokens | vLLM |
| `cmp-r1-distill-qwen-1.5b` | deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B | T 0.6, top-p 0.95, instructions in the user turn, 8,192 tokens | vLLM |
| `cmp-openreasoning-nemotron-1.5b` | nvidia/OpenReasoning-Nemotron-1.5B | T 0.6, top-p 0.95, instructions in the user turn, 8,192 tokens | vLLM |

Qwen/Qwen3-1.7B in thinking mode (`cmp-qwen3-1.7b-think`) was planned but not finished, so it is not in these reports.

Rebuild the figure: `python tools/make_compare_figure.py`.
