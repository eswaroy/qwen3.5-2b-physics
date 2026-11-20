---
license: cc-by-nc-sa-4.0
base_model: Qwen/Qwen3.5-2B
library_name: transformers
pipeline_tag: text-generation
language:
- en
tags:
- physics
- ugphysics
- science
- qwen3.5
- lora
datasets:
- MegaScience/MegaScience
- IUTVanguard/PhysicsEval
---

# Qwen3.5-2B Physics (non-thinking)

A physics fine-tune of [Qwen3.5-2B](https://huggingface.co/Qwen/Qwen3.5-2B), trained on a free Google Colab T4. It solves undergraduate physics problems with short step-by-step reasoning and a boxed final answer.

On **1,142 held-out UGPhysics questions** it scores **18.9%**, the best of the five open 1.5–2B models tested in the same harness: ahead of base Qwen3.5-2B (15.9%), MegaScience's Qwen3-1.7B (12.6%), DeepSeek-R1-Distill-Qwen-1.5B (9.8%) and OpenReasoning-Nemotron-1.5B (5.0%), each by a statistically significant margin. Its answers are 2.7× shorter than the base model's. It is weaker at hard competition maths (see [Limitations](#limitations)).

![Bar charts. UGPhysics held-out test: this model 18.9%, Qwen3.5-2B 15.9%, MegaScience Qwen3-1.7B 12.6%, DeepSeek-R1-Distill-Qwen-1.5B 9.8%, OpenReasoning-Nemotron-1.5B 5.0%. MATH-500: 63.5%, 73.0%, 63.0%, 78.2%, 54.7%.](assets/compare_card.png)

Code, every generated answer and the full reports: [GitHub](https://github.com/eswaroy/qwen3.5-2b-physics).

## Results

All numbers come from one harness: UGPhysics (English) with its official prompt and rule-based judge, greedy decoding, at most 4,096 new tokens, float16 on a Tesla T4. UGPhysics accuracy is weighted by subject size. Only the rule judge is used, not the official two-stage protocol with an LLM judge (MARJ), so these numbers are not directly comparable with the UGPhysics leaderboard.

### Final test: questions never used for any decision

UGPhysics English, the questions ranked 100 to 199 in each subject: 12 subjects, 1,142 questions (GeometricalOptics has none left).

| model | accuracy [95% CI] | mean answer length | hit the 4,096-token limit |
|---|---|---|---|
| Qwen3.5-2B, non-thinking | 15.9% [13.6, 18.5] | 2,720 tokens | 48.9% |
| **this model** | **18.9% [16.3, 21.7]** | 1,006 tokens | 6.9% |

Paired difference: **+3.0 points** [+0.3, +5.7] (paired bootstrap 95% interval). This model is right on 102 questions the base model gets wrong and wrong on 75 that the base model gets right (exact McNemar p = 0.050).

### Comparison with other small open models

The same 1,142 held-out questions and 210 MATH-500 problems, the same prompts and the same rule judge for every model. Each model used its developer's recommended decoding; the two reasoning models were sampled (temperature 0.6, top-p 0.95) and got **8,192 new tokens, twice this model's budget**.

| # | model | decoding | UGPhysics held-out [95% CI] | this model ahead by [95% CI] | wins / losses | MATH-500 |
|---|---|---|---|---|---|---|
| 1 | **this model** | greedy, 4,096 tokens | **18.9%** [16.3, 21.7] | – | – | 63.5% |
| 2 | [Qwen/Qwen3.5-2B](https://huggingface.co/Qwen/Qwen3.5-2B), non-thinking | greedy, 4,096 tokens | 15.9% [13.6, 18.5] | +3.0 [+0.3, +5.7] | 102 / 75 | 73.0% |
| 3 | [MegaScience/Qwen3-1.7B-MegaScience](https://huggingface.co/MegaScience/Qwen3-1.7B-MegaScience) | greedy, 4,096 tokens | 12.6% [10.5, 15.0] | +6.3 [+3.7, +8.9] | 118 / 46 | 63.0% |
| 4 | [deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B) | sampled, 8,192 tokens | 9.8% [7.8, 11.9] | +9.1 [+6.4, +11.8] | 143 / 39 | **78.2%** |
| 5 | [nvidia/OpenReasoning-Nemotron-1.5B](https://huggingface.co/nvidia/OpenReasoning-Nemotron-1.5B) | sampled, 8,192 tokens | 5.0% [3.5, 6.5] | +13.9 [+11.3, +16.6] | 174 / 19 | 54.7% |

"Wins / losses": questions only this model got right vs questions only the other model got right (exact McNemar p = 0.050 against the base model and p < 0.001 against the other three). Against the three outside models, this model is ahead in 10 of 12 physics subjects and level in one.

The reasoning models think at great length on undergraduate physics: even with 8,192 tokens, R1-Distill never reached a final answer on 50% of the questions and Nemotron on 83%, while this model used 1,006 tokens on average and finished 92% of its answers. They may score higher with much longer budgets, which was not tested. On MATH-500 the order changes: R1-Distill leads, and this model is level with MegaScience's model. Qwen3-1.7B (thinking mode) was planned but not finished, so no claim is made about it. The results of this model and the base model come from transformers, the others from vLLM, with identical prompts and grading.

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

Full reports: [`eval/summary_final_test.md`](eval/summary_final_test.md), [`eval/summary_dev_all.md`](eval/summary_dev_all.md), and for the comparison [`eval/compare_leaderboard.md`](eval/compare_leaderboard.md), [`eval/summary_compare_ugphysics.md`](eval/summary_compare_ugphysics.md) and [`eval/summary_compare_math500.md`](eval/summary_compare_math500.md).

## How to use

Use the non-thinking chat format and greedy decoding, as in the evaluation.

```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

repo = "eswaroy/qwen3.5-2b-physics"
tok = AutoTokenizer.from_pretrained(repo)
model = AutoModelForCausalLM.from_pretrained(repo, dtype=torch.float16, device_map="auto")

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

The weights are stored in float16, the precision used for every evaluation. Loading them as bfloat16 also works but rounds part of the fine-tune's small weight changes away, so answers can differ slightly from the reported results. Qwen3.5 needs a recent `transformers` (`pip install -U transformers`).

**Adapter only:** the half-strength LoRA adapter is in [`adapter/`](adapter). To apply it to the original model with PEFT:

```python
from peft import PeftModel
base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen3.5-2B", dtype=torch.float16, device_map="auto")
model = PeftModel.from_pretrained(base, "eswaroy/qwen3.5-2b-physics", subfolder="adapter").merge_and_unload()
```

## Training

- **Data:** 29,500 step-by-step solutions built mainly from [MegaScience](https://huggingface.co/datasets/MegaScience/MegaScience) (textbook physics, physics questions from NaturalReasoning, Nemotron-Science physics multiple choice, and some maths), plus the [PhysicsEval](https://huggingface.co/datasets/IUTVanguard/PhysicsEval) training split. Every question that overlapped a UGPhysics, PhysicsEval-test or MATH-500 question was removed (same text, a shared 13-word run, TF-IDF similarity of 0.4 or more, or a reworded copy with the same numbers). A random 12,000 of them were used.
- **Format:** Qwen's non-thinking chat format. The reasoning is plain text, followed by `So the final answer is \boxed{...}`. The loss covers the answer only.
- **Method:** LoRA, rank 32, alpha 64, on the attention (`q_proj`, `k_proj`, `v_proj`, `o_proj`), Gated DeltaNet (`in_proj_qkv`, `in_proj_z`, `out_proj`) and MLP (`gate_proj`, `up_proj`, `down_proj`) layers: 31M trainable parameters. Learning rate 1e-4 with 5% warm-up and cosine decay, about 18 examples per step, 647 steps (1 epoch), fp16 with loss scaling. About 4.5 hours on one T4.
- **Half strength:** the adapter is applied at 0.5× (alpha 32) before merging. At full strength the answers became too short for hard problems (MATH-500 fell to 51.7% on 70 questions); half strength kept the physics gain.
- **Text only:** Qwen3.5-2B's vision encoder is not included.

## Limitations

- About 4 of every 5 undergraduate physics problems are still answered wrongly. Always check the answers.
- Worse than the base model on hard maths (see MATH-500 above), and well behind DeepSeek-R1-Distill-Qwen-1.5B there (63.5% vs 78.2%). Use a reasoning model for competition maths.
- Compared with five open models only; Qwen3-1.7B in thinking mode and other families (Gemma, SmolLM, Phi) were not tested.
- About 7% of answers still run past 4,096 tokens.
- English only. Evaluated only with greedy decoding.

## License

Released under **CC BY-NC-SA 4.0** (non-commercial, share-alike), the most restrictive licence among its sources: the base model Qwen3.5-2B is Apache-2.0, most of the training data comes from MegaScience (CC BY-NC-SA 4.0), and the PhysicsEval training split is CC BY-SA 4.0.

## Acknowledgements

The Qwen team (Qwen3.5-2B), the UGPhysics authors (benchmark and grader), and the creators of MegaScience and PhysicsEval.
