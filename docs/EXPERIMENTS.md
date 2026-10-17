# Experiment log

[← back to README](../README.md)

The goal: fine-tune a small open model on free Colab T4 GPUs so that it beats comparable models at undergraduate physics, measured honestly. This page records every experiment in order, including the ones that failed, because the failures decided the final recipe.

Unless noted, "UGPhysics" means the development slice (ranks 0 to 99 per subject). Early checkpoints were screened on its first 20 questions per subject (260 questions) and MATH-500's first 10 per subject (70 questions); promising ones were then run on more. All runs use greedy decoding and 4,096 new tokens.

## Summary

| # | Model and training | UGPhysics | MATH-500 | Verdict |
|---|---|---|---|---|
| 0a | LFM2.5-1.2B-Thinking, no training | 13.3% (260) · 11.3% (1,258) | 67.5% (70) | baseline |
| 0b | Qwen3.5-2B non-thinking, no training | 17.5% (260) · 14.5% (1,008) | 67.1% (70) · 73.0% (210) | stronger baseline |
| 0c | Qwen3.5-2B thinking, no training | 0.0% (672) | – | never finishes thinking within 4,096 tokens |
| 1 | LFM + short teacher solutions (v1.2), 600 steps | 5.5% (260) | 46.8% (70) | reasoning collapsed |
| 2 | LFM + its own correct answers (self2), 293 steps | 10.9% (260) | 66.5% (70) | no gain |
| 3 | Qwen non-thinking + v1.2, full strength, 647 steps | 19.0% (260) · 16.5% (1,258) | 51.7% (70) | physics up, maths down |
| 4 | Same adapter at half strength | 17.3% (260) · 18.3% (1,258) | 69.4% (70) · 63.5% (210) | **chosen** |
| 5 | Final test of #4 vs #0b, held-out slice | **18.9% vs 15.9%** (1,142) | – | gain confirmed |

## 0. Baselines and the evaluation harness

Before training anything, [`physeval.py`](../src/physeval.py) was built to reproduce the UGPhysics protocol on a T4: the official prompt and rule judge (pinned to a fixed commit of the UGPhysics repository), subject-weighted accuracy, bootstrap intervals, paired tests, a loop detector, and a check that padded batches give the same outputs as single prompts.

- **LFM2.5-1.2B-Thinking** (the first target, as a ~1B model): 11.3% on 1,258 questions. 61% of its answers hit the 4,096-token limit while still thinking. Doubling the budget to 8,192 tokens only raised the 260-question score from 13.3% to 14.5%, so the budget was not the main problem.
- **Qwen3.5-2B, non-thinking**: 14.5% on 1,008 questions, but 52% of answers ran past the limit and 42% had no boxed answer. It rambles rather than thinks.
- **Qwen3.5-2B, thinking**: 0 of 672. It never closed its thinking section (74% hit the limit, 26% looped).

## 1. Short teacher solutions on a thinking model (LFM)

**Data.** [`physdata.py`](../src/physdata.py) built three versions of the training set (v1: 26,865 examples, v1.1 and v1.2: 29,500). v1.2 added physics questions from NaturalReasoning, a subject classifier, subject quotas weighted toward the base model's weak subjects, a stricter leak check (reworded copies with the same numbers), and a check of every solution's answer against its reference with the official grader. The solutions are short: median 763 tokens in total.

**Training.** [`phystrain.py`](../src/phystrain.py) with LoRA and DoRA pilots. DoRA was about 1.75× slower per step on a T4, so LoRA (rank 32) was used. The solutions were wrapped in LFM's `<think> … </think>` format.

**Result at step 600.** The format was fixed (97% of answers finished), but UGPhysics fell from 13.3% to 5.5% and MATH-500 from 67.5% to 46.8%.

**Lesson.** Teaching a thinking model to think in 500 tokens removes the long reasoning it relies on. Short solutions are the wrong target for a model that was trained to think long.

## 2. Self-distillation (LFM)

**Idea.** Keep the model's own reasoning style and only teach it to finish: generate answers with the base model, keep the correct ones, and train on them. [`physself.py`](../src/physself.py) generated 18,000 answers for 9,000 training questions with vLLM on three T4s in parallel.

- Only 15% of the answers were correct, and 7.9% of questions got at least one correct answer, mostly in maths. Physics questions with a correct answer were rare (about 1%).
- Round 1 (`self1`) answers often argued with the prompt about the answer format. Round 2 (`self2`) generated with a plain prompt and trained under the official prompt (context distillation), with stricter filters; 2,437 examples.

**Result at step 293.** UGPhysics 10.9% (base 13.3%), MATH-500 66.5% (base 67.5%), and 71% of answers still hit the limit.

**Lesson.** Self-distillation kept the reasoning intact (maths unchanged) but added no physics: the model rarely solves these problems, so there is little correct material to learn from. LFM's limit is physics skill, not format.

## 3. Switch to Qwen3.5-2B, non-thinking

**Why.** Qwen3.5-2B was already ahead (14.5% vs 11.3%), and in non-thinking mode it writes visible step-by-step reasoning, the same style as the v1.2 solutions. Its main weakness was format (rambling past the limit), which short solutions should fix without fighting a thinking habit.

**Trainer changes (phystrain 1.4).**
- LoRA on Qwen3.5's three layer types: full attention (`q/k/v/o_proj`), Gated DeltaNet linear attention (`in_proj_qkv`, `in_proj_z`, `out_proj`) and MLP; 31M trainable parameters.
- Prompts rendered exactly as at evaluation (`enable_thinking=False`, an empty `<think></think>` block), without LFM's system message; reasoning trained as plain text.
- The loss over Qwen's 248K-token vocabulary is computed in chunks that are recomputed in the backward pass, so the logits never fill the GPU.
- A random 12,000 of the 29,500 examples (one epoch is about 4.5 hours on a T4).

**Speed test.** With gradient checkpointing: about 21 s per step and 5.0 GB peak memory; without it: out of memory. Raising the forward-pass size from 2,048 to 8,192 tokens changed little (about 1.3 s per example either way). The run took 647 steps and was continued on a second account after the first ran out of GPU time.

**Result.** Validation loss ended at 0.295 (0.375 after 20 steps in the speed test; 0.2952 at step 600, 0.2949 at step 647). Checkpoints on 260 questions: step 250 16.7%, step 500 16.1%, step 647 19.0%. On 1,008 questions the final checkpoint scored 16.6% vs 14.5% for the base model (p = 0.071, not yet conclusive). Answers became short (median 516 tokens) and almost all finished, but MATH-500 fell from 67.1% to 51.7%, and to 13% on the hardest level.

**Lesson.** The format problem was solved, but the answers became too short for hard problems.

## 4. Half-strength adapter

**Idea.** A LoRA adapter adds a learned change ΔW to each weight. Scaling it by 0.5 (here: `lora_alpha` 64 → 32, no retraining) gives a model halfway between the base and the fine-tune. Interpolations like this often keep most of a fine-tune's gain while losing less of the base model's other skills.

**Result.**
- MATH-500 (70): 69.4%, back at the base model's level (67.1%); hard problems recovered from 13% to 33%.
- UGPhysics on 1,008 questions: **17.9% vs 14.5%** for the base model, +3.3 points, p = 0.0035, larger than at full strength.
- Answers stayed mostly short (median 710 tokens), with 7.7% hitting the limit.

## 5. Final test

The half-strength model was chosen on the development questions, so its score there is slightly optimistic. The questions ranked 100 to 199 in each subject (1,142 questions in 12 subjects) had never been looked at.

- **UGPhysics: 18.9% vs 15.9%**, +3.0 points [+0.3, +5.7], 102 wins vs 75 losses (McNemar p = 0.050). The gain matches the development result.
- **MATH-500 on 210 questions: 63.5% vs 73.0%.** With three times more maths questions, a real maths loss of 9.4 points appeared (p = 0.044), mostly at Level 5 (49% → 26%). The 70-question result had been optimistic.

## 6. Publishing

The adapter was merged into Qwen3.5-2B in float32 and saved in **float16**, the precision of every evaluation. A first merge saved in bfloat16 changed 9 of 26 answers on a check set: bfloat16 keeps only 8 bits of precision, so part of the small LoRA change was rounded away. The published weights are therefore float16, and [`PhysicsPublish.ipynb`](../notebooks/PhysicsPublish.ipynb) compares the merged model's answers with the adapter's own before upload. The adapter is published too, for use with PEFT.

## What would come next

- **Fix the maths loss** by training on the model's own correct long answers for hard problems, or by mixing longer solutions into the data.
- **More physics skill** needs better solutions than the short textbook ones: for example, verified long-form solutions from a stronger teacher.
- **Compare with other small models** (Qwen3-1.7B, DeepSeek-R1-Distill-Qwen-1.5B, MegaScience's Qwen3-1.7B fine-tune) in the same harness. A fresh held-out slice is still available: UGPhysics questions ranked 200 and above have never been used.
