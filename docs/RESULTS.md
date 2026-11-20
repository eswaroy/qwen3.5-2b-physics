# Results

[← back to README](../README.md)

Every number on this page comes from the same harness ([`src/physeval.py`](../src/physeval.py)): the official UGPhysics prompt and rule-based judge, greedy decoding, at most 4,096 new tokens, float16 on a Tesla T4, batches of 16. The raw reports are in [`results/reports/`](../results/reports), and every generated answer is in [`results/runs/`](../results/runs).

**How to read the numbers**

- **Accuracy** on UGPhysics is weighted by each subject's share of the full 5,520-question English set, so a subject with few questions in a slice does not distort the total.
- **[brackets]** are 95% intervals from a stratified bootstrap (2,000 resamples within each subject).
- **Comparisons** use only the questions both models answered: a paired bootstrap interval for the difference, plus the exact McNemar test on the questions where exactly one model is right ("wins" vs "losses").
- **Rule judge only.** The UGPhysics paper's official protocol (MARJ) re-checks rule-judged failures with GPT-4o, which marks more answers correct. These numbers are therefore lower than, and not comparable with, the paper's leaderboard; they are comparable with each other.

## 1. Final test: held-out questions

UGPhysics English questions ranked 100 to 199 inside each subject (ranks come from a fixed hash). None of them was used for any decision: not for choosing checkpoints, not for the adapter strength, not for the training data (all UGPhysics questions were removed from the training data). GeometricalOptics has only 58 questions, all in the development slice, so the test covers 12 subjects.

| Model | Questions | Accuracy [95% CI] | Unweighted |
|---|---|---|---|
| Qwen3.5-2B, non-thinking | 1,142 | 15.9% [13.6, 18.5] | 15.7% |
| **This model** | 1,142 | **18.9%** [16.3, 21.7] | 18.0% |

**Difference: +3.0 points** [+0.3, +5.7]. This model is right on 102 questions the base model gets wrong and wrong on 75 that the base model gets right (exact McNemar p = 0.050).

### By subject (%)

| Subject | Questions | Base | This model |
|---|---|---|---|
| AtomicPhysics | 100 | 27.0 | 26.0 |
| ClassicalElectromagnetism | 100 | 16.0 | 15.0 |
| ClassicalMechanics | 100 | 16.0 | **26.0** |
| Electrodynamics | 84 | 10.7 | **17.9** |
| QuantumMechanics | 100 | 11.0 | **18.0** |
| Relativity | 100 | 21.0 | 20.0 |
| SemiconductorPhysics | 86 | 23.3 | **31.4** |
| Solid-StatePhysics | 72 | 11.1 | 11.1 |
| StatisticalMechanics | 100 | 8.0 | 6.0 |
| TheoreticalMechanics | 100 | 8.0 | 12.0 |
| Thermodynamics | 100 | 19.0 | 20.0 |
| WaveOptics | 100 | 16.0 | 13.0 |

### By reasoning skill and answer type (%)

| Reasoning skill | Questions | Base | This model |
|---|---|---|---|
| Knowledge recall | 105 | 32.4 | **41.9** |
| Laws application | 412 | 20.9 | 21.6 |
| Math derivation | 468 | 6.8 | 9.4 |
| Practical application | 117 | 18.8 | 20.5 |

| Answer type | Questions | Base | This model |
|---|---|---|---|
| Numerical value | 384 | 24.2 | 25.8 |
| Expression | 304 | 7.6 | 6.6 |
| Equation | 148 | 9.5 | **18.2** |
| Multiple choice | 35 | 25.7 | **68.6** |
| True/false | 32 | 68.8 | 56.2 |
| Interval | 12 | 8.3 | 0.0 |
| Several answers | 224 | 7.1 | 7.1 |

(Three questions with malformed answer-type labels in the dataset, and 40 without a reasoning-skill label, are left out of these two breakdowns.)

### How the answers end

| Model | Mean tokens | Median | 90th percentile | Finished normally | Hit the 4,096 limit | Stuck in a loop | No boxed answer |
|---|---|---|---|---|---|---|---|
| Base | 2,720 | 3,862 | 4,096 | 48.9% | 48.9% | 2.1% | 38.5% |
| This model | 1,006 | 726 | 1,782 | 91.7% | 6.9% | 1.4% | 8.1% |

The base model loses about half its answers to the token limit; this model finishes more than nine in ten.

<!-- compare:start -->
## Comparison with other small open models

Four other open models of 1.5 to 2B parameters answered **the same 1,142 held-out questions** and the same 210 MATH-500 problems, with the same prompts and the same rule judge ([`notebooks/PhysicsCompare.ipynb`](../notebooks/PhysicsCompare.ipynb)). Reports: [`results/compare/`](../results/compare).

| # | Model | Size | Decoding | UGPhysics held-out [95% CI] | This model ahead by [95% CI] | Wins / losses | p | MATH-500 [95% CI] |
|---|---|---|---|---|---|---|---|---|
| 1 | **This model** | 2B | greedy, 4,096 tokens | **18.9%** [16.3, 21.7] | – | – | – | 63.5% [56.6, 69.9] |
| 2 | Qwen/Qwen3.5-2B, non-thinking (base) | 2B | greedy, 4,096 tokens | 15.9% [13.6, 18.5] | +3.0 [+0.3, +5.7] | 102 / 75 | 0.050 | 73.0% [67.3, 78.7] |
| 3 | MegaScience/Qwen3-1.7B-MegaScience | 1.7B | greedy, 4,096 tokens | 12.6% [10.5, 15.0] | +6.3 [+3.7, +8.9] | 118 / 46 | < 0.001 | 63.0% [56.5, 69.1] |
| 4 | deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B | 1.5B | sampled, 8,192 tokens | 9.8% [7.8, 11.9] | +9.1 [+6.4, +11.8] | 143 / 39 | < 0.001 | **78.2%** [73.0, 83.7] |
| 5 | nvidia/OpenReasoning-Nemotron-1.5B | 1.5B | sampled, 8,192 tokens | 5.0% [3.5, 6.5] | +13.9 [+11.3, +16.6] | 174 / 19 | < 0.001 | 54.7% [47.8, 61.4] |

"Wins / losses": questions only this model answered correctly vs questions only the other model answered correctly; p is the exact McNemar test. Every paired interval excludes zero, so on held-out UGPhysics this model is ahead of all four.

**How each model was run.** Every model got its developer's recommended settings. MegaScience's model is a non-thinking fine-tune and was run like ours (greedy, 4,096 new tokens). The two reasoning models were sampled as their developers recommend (temperature 0.6, top-p 0.95, one sample per question with a fixed seed, instructions in the user turn) because greedy decoding makes them loop, and they got **8,192 new tokens, twice our budget**, as the UGPhysics paper gives o1-style models.

### By subject (%)

| Subject | Questions | This model | Qwen3.5-2B | MegaScience 1.7B | R1-Distill 1.5B | Nemotron 1.5B |
|---|---|---|---|---|---|---|
| AtomicPhysics | 100 | 26.0 | **27.0** | 20.0 | 10.0 | 10.0 |
| ClassicalElectromagnetism | 100 | 15.0 | **16.0** | 10.0 | 7.0 | 3.0 |
| ClassicalMechanics | 100 | **26.0** | 16.0 | 11.0 | 18.0 | 6.0 |
| Electrodynamics | 84 | **17.9** | 10.7 | 9.5 | 7.1 | 4.8 |
| QuantumMechanics | 100 | **18.0** | 11.0 | 14.0 | 10.0 | 3.0 |
| Relativity | 100 | 20.0 | **21.0** | 3.0 | 7.0 | 1.0 |
| SemiconductorPhysics | 86 | **31.4** | 23.3 | 24.4 | 11.6 | 5.8 |
| Solid-StatePhysics | 72 | **11.1** | **11.1** | 8.3 | 5.6 | 4.2 |
| StatisticalMechanics | 100 | 6.0 | **8.0** | 6.0 | 4.0 | 3.0 |
| TheoreticalMechanics | 100 | **12.0** | 8.0 | 10.0 | 5.0 | 1.0 |
| Thermodynamics | 100 | **20.0** | 19.0 | 11.0 | 8.0 | 7.0 |
| WaveOptics | 100 | 13.0 | **16.0** | 14.0 | 13.0 | 5.0 |

Against the three outside models, this model is ahead in 10 of 12 subjects, level in StatisticalMechanics and behind only in WaveOptics (MegaScience 14.0 vs 13.0).

| Reasoning skill | Questions | This model | Qwen3.5-2B | MegaScience 1.7B | R1-Distill 1.5B | Nemotron 1.5B |
|---|---|---|---|---|---|---|
| Knowledge recall | 105 | **41.9** | 32.4 | 34.3 | 20.0 | 19.0 |
| Laws application | 412 | **21.6** | 20.9 | 14.1 | 12.4 | 5.1 |
| Math derivation | 468 | **9.4** | 6.8 | 5.3 | 3.8 | 1.7 |
| Practical application | 117 | **20.5** | 18.8 | 6.8 | 6.8 | 0.0 |

### How the answers end (UGPhysics held-out)

| Model | Mean new tokens | Finished normally | Hit the token limit | Never finished thinking |
|---|---|---|---|---|
| **This model** | **1,006** | **91.7%** | 6.9% | – |
| Qwen3.5-2B (base) | 2,720 | 48.9% | 48.9% | – |
| MegaScience 1.7B | 1,515 | 86.0% | 13.6% | 0.4% |
| R1-Distill 1.5B | 6,460 | 47.4% | 52.4% (of 8,192) | 50.2% |
| Nemotron 1.5B | 7,762 | 15.7% | 83.5% (of 8,192) | 82.8% |

The reasoning models think for a very long time on undergraduate physics: even with 8,192 tokens, R1-Distill never reached a final answer on half of the questions and Nemotron on more than four in five. They would probably score higher with 16K to 32K tokens, which was not tested (at 8,192 tokens they already needed 7.2 and 9.2 T4-hours for these questions). The fair summary is: **at the budget a free T4 can afford, this model gives the most correct physics answers, using 6 to 8 times fewer tokens than the reasoning models.**

### MATH-500

On maths the order changes: R1-Distill-Qwen-1.5B leads (78.2%), followed by the base model (73.0%). This model (63.5%) is level with MegaScience's model (63.0%, p = 0.78) and ahead of OpenReasoning-Nemotron-1.5B (54.7%, +8.8 [+1.9, +16.2], p = 0.012). Training on short physics solutions costs maths ability on the hardest problems (Level 5: 26.4%, vs 54.7% for R1-Distill); this is the main trade-off of the model.

### Caveats

- **Qwen3-1.7B (thinking mode) was planned but not finished**: loading and generating with it took too long on the free T4 within our sessions, so no claim is made about it. Other models of this size (for example Gemma, SmolLM or Phi models) were not tested either.
- **Different engines.** The results of this model and base Qwen3.5-2B are the earlier ones, made with transformers; the other models ran on vLLM, a faster engine. Prompts, questions and grading are identical; tiny numerical differences between engines do not change greedy answers often enough to affect these gaps.
- **One sample** per question for the sampled models; a different seed would move their scores by about a point, well inside the intervals.
- **Rule judge only**, as everywhere in this repository: lower than and not comparable with the UGPhysics paper's GPT-4o-assisted leaderboard.
<!-- compare:end -->

## 2. Development questions

UGPhysics English questions ranked 0 to 99 inside each subject (1,258 questions). These were used to choose between training runs, checkpoints and adapter strengths, so scores here are slightly optimistic for the chosen model.

| Model | Questions answered | Accuracy [95% CI] |
|---|---|---|
| LiquidAI/LFM2.5-1.2B-Thinking | 1,258 | 11.3% [9.1, 13.5] |
| Qwen3.5-2B, thinking mode | 672 | 0.0% [0.0, 0.0] |
| Qwen3.5-2B, non-thinking | 1,008 | 14.5% [11.9, 17.3] |
| Qwen3.5-2B + adapter, full strength | 1,258 | 16.5% [14.0, 18.9] |
| **Qwen3.5-2B + adapter, half strength (this model)** | 1,258 | **18.3%** [15.6, 20.9] |

Paired comparisons on the questions both answered:

| A | B | Questions | A | B | B − A [95% CI] | B wins / A wins | p |
|---|---|---|---|---|---|---|---|
| Base, non-thinking | Full strength | 1,008 | 14.5 | 16.6 | +2.0 [−0.8, +5.1] | 86 / 63 | 0.071 |
| Base, non-thinking | **Half strength** | 1,008 | 14.5 | 17.9 | **+3.3** [+0.4, +6.4] | 86 / 51 | **0.0035** |
| Full strength | Half strength | 1,258 | 16.5 | 18.3 | +1.8 [−0.4, +4.1] | 75 / 55 | 0.095 |

**Thinking mode.** With greedy decoding and 4,096 tokens, Qwen3.5-2B in thinking mode never closed its thinking section on any of 672 questions: 74.4% hit the limit and 25.6% were stopped as repetition loops. In this harness only the answer after the thinking section counts, so drafts inside the unfinished thinking score nothing and the model scores 0%. It may do much better with a far larger budget and sampling; that was not tested.

### By subject (%), development questions

| Subject | Questions | Base | This model |
|---|---|---|---|
| AtomicPhysics | 100 | 22.8 | 31.0 |
| ClassicalElectromagnetism | 100 | 10.1 | 15.0 |
| ClassicalMechanics | 100 | 16.7 | 15.0 |
| Electrodynamics | 100 | 12.3 | 13.0 |
| GeometricalOptics | 58 | 15.5 | 17.2 |
| QuantumMechanics | 100 | 15.0 | 17.0 |
| Relativity | 100 | 10.3 | 10.0 |
| SemiconductorPhysics | 100 | 16.5 | 25.0 |
| Solid-StatePhysics | 100 | 15.2 | 15.0 |
| StatisticalMechanics | 100 | 6.2 | 9.0 |
| TheoreticalMechanics | 100 | 3.8 | 10.0 |
| Thermodynamics | 100 | 13.6 | 19.0 |
| WaveOptics | 100 | 18.4 | 29.0 |

(The base model answered 1,008 of these questions, so its per-subject numbers rest on about 80 questions each.)

## 3. MATH-500 (regression check)

210 questions, 30 per subject, graded with the same rule judge. Use it to compare these runs with each other, not with published MATH-500 numbers, which use other graders.

| Model | Accuracy [95% CI] |
|---|---|
| LiquidAI/LFM2.5-1.2B-Thinking | 67.7% [61.4, 73.8] |
| Qwen3.5-2B, non-thinking | **73.0%** [67.3, 78.7] |
| This model | 63.5% [56.6, 69.9] |

Difference to the base model: **−9.4 points** [−16.5, −2.6]; the base model wins 36 questions, this model 20 (p = 0.044). The loss is concentrated on the hardest problems:

| Level | Questions | Base | This model |
|---|---|---|---|
| 1 | 17 | 70.6 | 88.2 |
| 2 | 39 | 84.6 | 76.9 |
| 3 | 42 | 71.4 | 78.6 |
| 4 | 59 | 72.9 | 61.0 |
| 5 | 53 | 49.1 | 26.4 |

Training on short solutions teaches the model to answer briefly. That suits most physics questions here but cuts the long reasoning that the hardest maths problems need. Halving the adapter's strength reduced this effect: on the first 70 of these questions, the full-strength adapter scored 51.7%, the half-strength one 69.4% and the base model 67.1%.

## 4. Cost

| Run | Questions | GPU hours (T4) | Tokens per second |
|---|---|---|---|
| Base, final test | 1,142 | 6.31 | 137 |
| This model, final test | 1,142 | 4.71 | 68 |

Shorter answers make this model about 25% cheaper per question to evaluate (Qwen3.5's linear-attention layers ran on transformers' slower reference implementation, because the optimized kernels were not installed.)
