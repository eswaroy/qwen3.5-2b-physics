# Evaluation results

Produced by [`src/physeval.py`](../src/physeval.py). A readable summary is in [docs/RESULTS.md](../docs/RESULTS.md).

| Path | Content |
|---|---|
| `reports/summary_final_test.md` | **main result**: this model vs base Qwen3.5-2B on the 1,142 held-out questions |
| `reports/summary_dev_all.md` | development questions: all baselines and this model, MATH-500 on 210 questions |
| `reports/summary_*.md` | the other reports saved during the project |
| `final_test/`, `dev/` | `summary.json` (every number in machine-readable form) and `tables/` (CSV breakdowns) for the two main reports |
| `runs/<run>/meta.json` | settings of a run: model, adapter, chat-template options, budget, GPU, library versions |
| `runs/<run>/gen_<benchmark>.jsonl.gz` | every generated answer (question ID, full text, token counts, finish reason) |
| `runs/<run>/graded_<benchmark>.jsonl.gz` | grading of every answer (extracted answer, rule-judge verdict, normalised reference) |

The benchmark questions themselves are not stored here; they are identified by `uid` and can be loaded from the original datasets with `physeval.py prepare`.

## Run names

| Run | Model |
|---|---|
| `lfm25-1.2b-thinking` | LiquidAI/LFM2.5-1.2B-Thinking (`-8k`: 8,192-token budget) |
| `qwen35-2b-nothink` | Qwen3.5-2B, non-thinking, development questions (`-test`: held-out test) |
| `qwen35-2b-think` | Qwen3.5-2B, thinking mode |
| `ft-v1.2-lora-s600` | experiment 1: LFM2.5 + short solutions, step 600 |
| `ft-self2-lora-s293` | experiment 2: LFM2.5 + self-distillation, step 293 |
| `ft-qwen-v1.2-lora-s250`, `-s500`, `-s647` | experiment 3: Qwen3.5-2B + v1.2 at full strength, by checkpoint |
| `ft-qwen-v1.2-lora-s647-x50` | **the released model** (half strength), development questions (`-test`: held-out test) |
| `merged-check-*` | the merged model, checked against the adapter before upload |
