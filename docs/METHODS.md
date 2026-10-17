# Methods

[← back to README](../README.md)

## 1. Evaluation

Implemented in [`src/physeval.py`](../src/physeval.py) (commands `prepare`, `generate`, `grade`, `judge`, `report`, `selftest`).

### Benchmarks

| Benchmark | Used for | Size | Grading |
|---|---|---|---|
| [UGPhysics](https://github.com/YangLabHKUST/UGPhysics), English | main score | 5,520 problems, 13 subjects | official rule-based judge |
| [MATH-500](https://huggingface.co/datasets/HuggingFaceH4/MATH-500) | regression check | 500 problems, 7 subjects | the same rule judge |
| [PhysicsEval](https://github.com/areebuzair/PhysicsEval) | supported, not used in the final results | 1,962 test problems | LLM judge with the official rubric |

### Development and test slices

Inside each subject, every question gets a fixed rank from a hash of its ID. Nothing about the questions decides the rank, so each slice is a random sample of its subject.

| Slice | Ranks per subject | Questions | Used for |
|---|---|---|---|
| Development | 0 to 99 | 1,258 | every decision: data settings, training runs, checkpoints, adapter strength |
| Screening subset | 0 to 19 | 260 | quick checkpoint screening (part of development) |
| **Held-out test** | 100 to 199 | 1,142 | the final comparison, run once |
| Unused | 200 and above | about 3,100 | kept for future work |

GeometricalOptics has only 58 questions, so it has no test questions. MATH-500 uses the same ranking (10 or 30 per subject).

### Generation

- The official UGPhysics prompt: system message `Please reason step by step, and put your final answer within \boxed{}.` plus the official user template for each answer type. Zero-shot.
- Greedy decoding, at most **4,096 new tokens** (the UGPhysics paper's budget for non-o1 models), repetition penalty 1.0.
- float16 on a Tesla T4 with Hugging Face `transformers`, batches of 16 with left padding. Before each run, the harness checks that padded batches give the same outputs as single prompts.
- A loop detector stops answers that repeat the same block over and over (they count as wrong).
- Chat-template options per model: Qwen3.5 with `enable_thinking=False` (non-thinking) or `True` (thinking).

### Grading and statistics

- **Rule judge**: the UGPhysics repository's own extraction and comparison code (pinned commit): the `\boxed{}` answers are compared with the reference as numbers (1% relative tolerance), expressions, equations, intervals, multiple-choice letters or true/false. Multi-answer questions need every part right. Only the text after a thinking section counts.
- The official protocol (MARJ) then sends rule-judge failures to GPT-4o. That second stage was not used (no paid API), so scores here are lower than the paper's and only comparable with each other.
- **Weighted accuracy**: each subject's accuracy weighted by its share of the full English set.
- **95% intervals**: stratified bootstrap, 2,000 resamples within each subject.
- **Paired comparisons** on the questions both runs answered: paired bootstrap interval of the difference and the exact McNemar test on discordant questions.

## 2. Training data (v1.2)

Built by [`src/physdata.py`](../src/physdata.py) in [`notebooks/PhysicsData.ipynb`](../notebooks/PhysicsData.ipynb). Statistics of the build are in [`data/v1.2/stats.md`](../data/v1.2/stats.md).

### Sources

| Source | Examples | Share |
|---|---|---|
| MegaScience, textbook physics | 17,548 | 59.5% |
| MegaScience, NaturalReasoning physics questions | 7,390 | 25.1% |
| MegaScience, maths | 2,943 | 10.0% |
| MegaScience, Nemotron-Science physics (multiple choice) | 1,298 | 4.4% |
| PhysicsEval, training split | 321 | 1.1% |
| **Total (train)** | **29,500** | |

Plus 500 validation examples. All rows come from [MegaScience](https://huggingface.co/datasets/MegaScience/MegaScience) (CC BY-NC-SA 4.0) and the [PhysicsEval](https://huggingface.co/datasets/IUTVanguard/PhysicsEval) training split (CC BY-SA 4.0).

### Pipeline

1. **Physics filter.** A naive Bayes classifier trained on MegaScience's subject labels picks physics questions from the mixed NaturalReasoning and Nemotron pools (88% of true physics questions kept in 5-fold cross-validation).
2. **Subject tagger.** A second classifier assigns each question one of the 13 UGPhysics subjects (73% correct in 5-fold cross-validation on the development questions' subject labels, vs 45% for keyword rules). It only sets the subject quotas; no benchmark text enters the training data.
3. **Clean-up.** Removed: questions that need a figure, table or handbook value; proofs; duplicates; references too long to check; solutions over 2,048 tokens in total or 1,600 tokens of reasoning.
4. **Leak check.** Every candidate is compared with **every** question of UGPhysics (all 5,520), MATH-500 (all 500) and the PhysicsEval test split. A candidate is removed for the same text, a shared run of 13 words, TF-IDF cosine similarity of 0.4 or more, or similarity of 0.3 or more together with two or more identical problem numbers (a reworded copy of the same exercise). 1,781 of 157,777 candidates were removed (110 exact, 845 13-word, 792 TF-IDF, 34 same numbers).
5. **Subject quotas.** Each subject's share = its share of the exam × the base model's weakness in it, at least 2%.
6. **Grader check.** Each solution's own boxed answer is compared with the reference answer by the official UGPhysics grader (after normalising LaTeX). Of 43,170 checked candidates, 61.7% agreed; the ones that disagreed were dropped. Free-form references that cannot be checked automatically were allowed.
7. **Styles.** 71.9% exam-style questions with the official prompt, 12.0% plain questions, 10.0% maths, 5.0% short knowledge questions, 1.1% PhysicsEval.

Each example has a question (chat messages), a step-by-step solution (`think`) and a final line `So the final answer is \boxed{...}` (`answer`). Median length: 763 tokens in total.

## 3. Training

Implemented in [`src/phystrain.py`](../src/phystrain.py) (commands `check`, `train`, `sample`, `merge`), run from [`notebooks/PhysicsTrain.ipynb`](../notebooks/PhysicsTrain.ipynb).

| Setting | Value |
|---|---|
| Base model | Qwen/Qwen3.5-2B (text model only), non-thinking chat format |
| Method | LoRA, rank 32, alpha 64, dropout 0 |
| Layers | `q_proj`, `k_proj`, `v_proj`, `o_proj` (full attention, 6 layers); `in_proj_qkv`, `in_proj_z`, `out_proj` (Gated DeltaNet, 18 layers); `gate_proj`, `up_proj`, `down_proj` (MLP, 24 layers) |
| Trainable parameters | 31.3M (1.6% of 1.91B) |
| Data | random 12,000 of the 29,500 v1.2 examples (seed 3407); 11,975 fit in 2,048 tokens |
| Target | `solution + "\n\n" + final answer + <|im_end|>`; loss on these tokens only, averaged over all answer tokens in a step |
| Batching | examples sorted by length within shuffled groups of 512, packed into forward passes of up to 8,192 tokens (at most 8 examples), about 18 examples per optimizer step |
| Optimizer | AdamW (β 0.9 / 0.999, weight decay 0.01), learning rate 1e-4, 5% linear warm-up, cosine decay to 10%, gradient clipping 1.0 |
| Steps | 647 (1 epoch) |
| Precision | base weights fp16, adapter fp32, fp16 autocast with a gradient scaler (the T4 has no bf16) |
| Memory | gradient checkpointing; the cross-entropy over the 248K-token vocabulary is computed in chunks of about 270 positions that are recomputed in the backward pass; peak 7.4 of 14.6 GB |
| Time | about 25 s per step, about 4.5 hours on one T4, split over two Colab sessions (the run resumes from its last checkpoint on Drive) |
| Monitoring | validation loss on 200 held-out examples every 100 steps; a generation check on 8 validation questions every 250 steps |

### Half strength and merging

LoRA adds `ΔW = (alpha / rank) · B·A` to each adapted weight. The released model uses **alpha 32 instead of 64**, which applies half of the learned change. No retraining is involved; only `lora_alpha` in `adapter_config.json` changes.

The merge runs on the CPU in float32 (`W + 0.5·ΔW`) and saves the result in float16, the precision of every evaluation. Saving in bfloat16 would round away part of the small LoRA change.

## 4. Self-distillation (experiment 2 only)

[`src/physself.py`](../src/physself.py) samples answers from the base model with vLLM (temperature 0.6, top-p 0.95, 2 samples per question, up to 3,584 tokens), grades them with the official judge, keeps the shortest correct answer per question, and filters out answers that talk about the answer format, close the thinking section twice, or ramble after the final answer. It was used for the LFM2.5 experiments; see [EXPERIMENTS.md](EXPERIMENTS.md).
