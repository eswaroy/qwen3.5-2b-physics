---
license: cc-by-nc-sa-4.0
base_model: Qwen/Qwen3.5-2B
library_name: transformers
pipeline_tag: text-generation
language:
- en
tags:
- physics
- science
- qwen3.5
- lora
datasets:
- MegaScience/MegaScience
- IUTVanguard/PhysicsEval
---

# Qwen3.5-2B Physics (non-thinking)

A physics fine-tune of [Qwen3.5-2B](https://huggingface.co/Qwen/Qwen3.5-2B), trained on a free Google Colab T4. It solves undergraduate physics problems with short step-by-step reasoning and a boxed final answer.

On **held-out UGPhysics questions** it scores **18.9% vs 15.9%** for the base model in the same (non-thinking) mode, with answers about 2.7× shorter. It is weaker than the base model at hard competition maths (see [Limitations](#limitations)).

## Results

All numbers come from one harness: UGPhysics (English) with its official prompt and rule-based judge, greedy decoding, at most 4,096 new tokens, float16 on a Tesla T4. UGPhysics accuracy is weighted by subject size. Only the rule judge is used, not the official two-stage protocol with an LLM judge (MARJ), so these numbers are not directly comparable with the UGPhysics leaderboard.

### Final test: questions never used for any decision

UGPhysics English, the questions ranked 100 to 199 in each subject: 12 subjects, 1,142 questions (GeometricalOptics has none left).

| model | accuracy [95% CI] | mean answer length | hit the 4,096-token limit |
|---|---|---|---|
| Qwen3.5-2B, non-thinking | 15.9% [13.6, 18.5] | 2,720 tokens | 48.9% |
| **this model** | **18.9% [16.3, 21.7]** | 1,006 tokens | 6.9% |

Paired difference: **+3.0 points** [+0.3, +5.7] (paired bootstrap 95% interval). This model is right on 102 questions the base model gets wrong and wrong on 75 that the base model gets right (exact McNemar p = 0.050).

### Development questions (used to choose the checkpoint and the adapter strength)

UGPhysics English, the questions ranked 0 to 99 in each subject.

| model | questions | accuracy |
|---|---|---|
| LiquidAI/LFM2.5-1.2B-Thinking | 1,258 | 11.3% |
| Qwen3.5-2B, thinking mode | 672 | 0.0%* |
| Qwen3.5-2B, non-thinking | 1,008 | 14.5% |
| **this model** | 1,258 | **18.3%** |

On the 1,008 questions both answered, this model leads the non-thinking base model by +3.3 points (17.9% vs 14.5%, McNemar p = 0.0035).

\* With 4,096 tokens and greedy decoding, Qwen3.5-2B in thinking mode never finished thinking (74% of answers hit the limit, 26% were stopped as repetition loops), so it never gave a final answer. It may do much better with a far larger token budget and sampling, which was not tested.

### MATH-500 (regression check)

210 questions (30 per subject), same grader.

| model | accuracy [95% CI] |
|---|---|
| Qwen3.5-2B, non-thinking | 73.0% [67.3, 78.7] |
| this model | 63.5% [56.6, 69.9] |

The drop (−9.4 points, McNemar p = 0.044) is mostly on the hardest problems (Level 5: 49% → 26%).

Full reports: [`eval/summary_final_test.md`](eval/summary_final_test.md) and [`eval/summary_dev_all.md`](eval/summary_dev_all.md).

## How to use

Use the non-thinking chat format and greedy decoding, as in the evaluation.

```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

repo = "eswaroy/qwen3.5-2b-physics"
tok = AutoTokenizer.from_pretrained(repo)
model = AutoModelForCausalLM.from_pretrained(repo, dtype=torch.bfloat16, device_map="auto")

messages = [
    {"role": "system", "content": "Please reason step by step, and put your final answer within \\boxed{}."},
    {"role": "user", "content": "A 2.0 kg block slides from rest down a frictionless incline of height 1.5 m. "
                                "What is its speed at the bottom? Take g = 9.8 m/s^2."},
]
prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
inputs = tok(prompt, return_tensors="pt").to(model.device)
out = model.generate(**inputs, max_new_tokens=4096, do_sample=False)
print(tok.decode(out[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True))
```

On a GPU without bf16 support (such as a T4), use `dtype=torch.float16`. Qwen3.5 needs a recent `transformers` (`pip install -U transformers`).

## Training

- **Data:** 29,500 step-by-step solutions built mainly from [MegaScience](https://huggingface.co/datasets/MegaScience/MegaScience) (textbook physics, physics questions from NaturalReasoning, Nemotron-Science physics multiple choice, and some maths), plus the [PhysicsEval](https://huggingface.co/datasets/IUTVanguard/PhysicsEval) training split. Every question that overlapped a UGPhysics, PhysicsEval-test or MATH-500 question was removed (same text, a shared 13-word run, TF-IDF similarity of 0.4 or more, or a reworded copy with the same numbers). A random 12,000 of them were used.
- **Format:** Qwen's non-thinking chat format. The reasoning is plain text, followed by `So the final answer is \boxed{...}`. The loss covers the answer only.
- **Method:** LoRA, rank 32, alpha 64, on the attention (`q_proj`, `k_proj`, `v_proj`, `o_proj`), Gated DeltaNet (`in_proj_qkv`, `in_proj_z`, `out_proj`) and MLP (`gate_proj`, `up_proj`, `down_proj`) layers: 31M trainable parameters. Learning rate 1e-4 with 5% warm-up and cosine decay, about 18 examples per step, 647 steps (1 epoch), fp16 with loss scaling. About 4.5 hours on one T4.
- **Half strength:** the adapter is applied at 0.5× (alpha 32) before merging. At full strength the answers became too short for hard problems (MATH-500 fell to 51.7% on 70 questions); half strength kept the physics gain.
- **Text only:** Qwen3.5-2B's vision encoder is not included.

## Limitations

- About 4 of every 5 undergraduate physics problems are still answered wrongly. Always check the answers.
- Worse than the base model on hard maths (see MATH-500 above).
- About 7% of answers still run past 4,096 tokens.
- English only. Evaluated only with greedy decoding.

## License

Released under **CC BY-NC-SA 4.0** (non-commercial, share-alike), the most restrictive licence among its sources: the base model Qwen3.5-2B is Apache-2.0, most of the training data comes from MegaScience (CC BY-NC-SA 4.0), and the PhysicsEval training split is CC BY-SA 4.0.

## Acknowledgements

The Qwen team (Qwen3.5-2B), the UGPhysics authors (benchmark and grader), and the creators of MegaScience and PhysicsEval.
