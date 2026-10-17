# Training data

**License: [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).** The rows are derived from [MegaScience](https://huggingface.co/datasets/MegaScience/MegaScience) (CC BY-NC-SA 4.0) and the training split of [PhysicsEval](https://huggingface.co/datasets/IUTVanguard/PhysicsEval) (CC BY-SA 4.0). Credit their authors, do not use the data commercially, and share derivatives under the same license.

How the data was built: [docs/METHODS.md](../docs/METHODS.md#2-training-data-v12).

## Files

| Path | Content |
|---|---|
| `v1.2/train.jsonl.gz` | 29,500 training examples (gzip-compressed JSON lines) |
| `v1.2/val.jsonl.gz` | 500 validation examples |
| `v1.2/stats.md` | build report: sources, subjects, answer types, lengths, grader check, removals |
| `v1.2/samples.md` | a few examples of each style, as the model sees them |
| `v1.2/grader_drops.csv.gz` | solutions dropped because their answer disagreed with the reference |
| `*/stats.md` (other folders) | build reports of the earlier datasets and the self-distillation sets |

The leak report (`leak_report.csv`) is not included because it quotes benchmark questions.

## Fields

```json
{
  "id": "…",
  "source": "megascience_physics | naturalreasoning_physics | megascience_math | nemotron_physics | physicseval_train",
  "style": "ug | plain | math | knowledge | pe",
  "messages": [{"role": "system", "content": "…"}, {"role": "user", "content": "…"}],
  "think": "step-by-step solution",
  "answer": "So the final answer is \\boxed{…}.",
  "meta": {"answer_type": "NV", "topic": "ClassicalMechanics", "reference": "…", "check": "agrees", "tokens": {"prompt": 194, "think": 479, "answer": 71}, "leak_similarity": 0.12}
}
```

Some prompts contain the system message "You are a helpful assistant trained by Liquid AI." because the data was first built for LFM2.5. The Qwen trainer drops that message (`--no-thinking` mode); token counts in `meta` are LFM2.5 tokens.

## Load it

```python
import gzip, json, random
rows = [json.loads(line) for line in gzip.open("data/v1.2/train.jsonl.gz", "rt", encoding="utf-8")]
subset = random.Random(3407).sample(rows, 12000)   # the 12,000 examples the released model was trained on
print(len(rows), subset[0]["messages"][-1]["content"][:200])
```
