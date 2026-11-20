<div align="center">

# Qwen3.5-2B Physics

**A 2-billion-parameter model fine-tuned on free Google Colab T4 GPUs to solve undergraduate physics problems.**<br>
On 1,142 UGPhysics questions it never saw during development, it scores **18.9%**, first of the five open 1.5–2B models tested, ahead of its base model (15.9%), MegaScience's Qwen3-1.7B (12.6%), DeepSeek-R1-Distill-Qwen-1.5B (9.8%) and OpenReasoning-Nemotron-1.5B (5.0%).

[![Model on Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-model-ffcc4d)](https://huggingface.co/eswaroy/qwen3.5-2b-physics)
[![Base model](https://img.shields.io/badge/base-Qwen3.5--2B-6250d6)](https://huggingface.co/Qwen/Qwen3.5-2B)
[![Trained on](https://img.shields.io/badge/trained%20on-free%20Colab%20T4-F9AB00?logo=googlecolab&logoColor=white)](docs/REPRODUCE.md)
[![Code license](https://img.shields.io/badge/code-MIT-2a78d6)](LICENSE)
[![Model license](https://img.shields.io/badge/model-CC%20BY--NC--SA%204.0-52514e)](https://huggingface.co/eswaroy/qwen3.5-2b-physics)

[**Model**](https://huggingface.co/eswaroy/qwen3.5-2b-physics) ·
[**Results**](docs/RESULTS.md) ·
[**Comparison**](docs/RESULTS.md#comparison-with-other-small-open-models) ·
[**Methods**](docs/METHODS.md) ·
[**Experiment log**](docs/EXPERIMENTS.md) ·
[**Reproduce**](docs/REPRODUCE.md)

</div>

---

## Highlights

- **#1 of the five small open models tested on unseen physics questions.** Same 1,142 held-out UGPhysics questions, same prompts, same judge: its lead over every other model is statistically significant (all paired 95% intervals exclude zero).
- **+3.0 points over its own base model** (15.9% → 18.9%, interval +0.3 to +5.7). The same gain appeared first on the development questions (+3.3, p = 0.0035).
- **+6.3 points over MegaScience's own Qwen3-1.7B fine-tune**, trained on the same family of science data (118 questions won, 46 lost).
- **Beats reasoning models given twice the budget.** DeepSeek-R1-Distill-Qwen-1.5B and OpenReasoning-Nemotron-1.5B got 8,192 tokens and sampling; this model wins by +9.1 and +13.9 points with **6–8× fewer tokens**.
- **2.7× shorter answers than its base model.** 1,006 tokens on average instead of 2,720; only 7% of answers hit the token limit instead of 49%.
- **Honest trade-off.** Weaker at hard maths: MATH-500 63.5%, vs 73.0% for the base model and 78.2% for R1-Distill.
- **Built for free.** Data building, training (about 4.5 GPU hours on one T4) and every evaluation ran on free Colab notebooks.

## Leaderboard: open models of 1.5–2B parameters

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/compare_dark.png">
  <img alt="Horizontal bar charts. UGPhysics held-out test: this model 18.9%, Qwen3.5-2B 15.9%, MegaScience Qwen3-1.7B 12.6%, DeepSeek-R1-Distill-Qwen-1.5B 9.8%, OpenReasoning-Nemotron-1.5B 5.0%. MATH-500: 63.5%, 73.0%, 63.0%, 78.2%, 54.7%." src="docs/assets/compare_light.png" width="860">
</picture>

| # | Model | Decoding | UGPhysics held-out | This model ahead by [95% CI] | MATH-500 |
|---|---|---|---|---|---|
| 1 | **This model** (Qwen3.5-2B + LoRA) | greedy, 4,096 tokens | **18.9%** | – | 63.5% |
| 2 | [Qwen3.5-2B](https://huggingface.co/Qwen/Qwen3.5-2B), non-thinking | greedy, 4,096 tokens | 15.9% | +3.0 [+0.3, +5.7] | 73.0% |
| 3 | [MegaScience Qwen3-1.7B](https://huggingface.co/MegaScience/Qwen3-1.7B-MegaScience) | greedy, 4,096 tokens | 12.6% | +6.3 [+3.7, +8.9] | 63.0% |
| 4 | [DeepSeek-R1-Distill-Qwen-1.5B](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B) | sampled, 8,192 tokens | 9.8% | +9.1 [+6.4, +11.8] | **78.2%** |
| 5 | [OpenReasoning-Nemotron-1.5B](https://huggingface.co/nvidia/OpenReasoning-Nemotron-1.5B) | sampled, 8,192 tokens | 5.0% | +13.9 [+11.3, +16.6] | 54.7% |

Every model answered the same 1,142 held-out UGPhysics questions and 210 MATH-500 problems with the official prompt and rule judge, using its developer's recommended decoding; the reasoning models got twice our token budget. Even so, they never reached a final answer on 50% (R1-Distill) and 83% (Nemotron) of the physics questions, so they may do better with far longer budgets than a free T4 allows. Qwen3-1.7B was planned but not finished (too slow on the free T4), so no claim is made about it. Per-subject tables, answer lengths and caveats: [docs/RESULTS.md](docs/RESULTS.md#comparison-with-other-small-open-models).

## Results against the base model

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/results_dark.png">
  <img alt="Bar charts. UGPhysics unseen questions: base Qwen3.5-2B 15.9%, this model 18.9%. MATH-500: base 73.0%, this model 63.5%." src="docs/assets/results_light.png" width="780">
</picture>

| Benchmark | Questions | Qwen3.5-2B (non-thinking) | **This model** | Difference |
|---|---|---|---|---|
| UGPhysics, held-out test | 1,142 | 15.9% [13.6, 18.5] | **18.9%** [16.3, 21.7] | **+3.0** [+0.3, +5.7] |
| UGPhysics, development | 1,008 | 14.5% | **17.9%** | +3.3 (p = 0.0035) |
| MATH-500 (regression check) | 210 | **73.0%** | 63.5% | −9.4 (p = 0.044) |

All runs: official UGPhysics prompt and rule-based judge, greedy decoding, at most 4,096 new tokens, float16 on a Tesla T4; UGPhysics scores are weighted by subject size; brackets are 95% intervals. Other models on the development questions: Qwen3.5-2B in thinking mode **0.0%** (it never closed its thinking within 4,096 tokens), LFM2.5-1.2B-Thinking **11.3%**.

These numbers use only the rule judge, not the official two-stage protocol with a GPT-4o judge, so they are not directly comparable with the UGPhysics paper's leaderboard. Full tables, per-subject results and statistics: [docs/RESULTS.md](docs/RESULTS.md).

## Quick start

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

Use the non-thinking chat format and greedy decoding, as in the evaluation. Qwen3.5 needs a recent `transformers` (`pip install -U transformers`).

## How it was built

```mermaid
flowchart LR
    A["MegaScience + PhysicsEval train<br/>157,777 candidate problems"] --> B["Filter<br/>physics classifier, length,<br/>figures, proofs, duplicates"]
    B --> C["Remove anything resembling<br/>a test question<br/>(UGPhysics, MATH-500, PhysicsEval)"]
    C --> D["Check each solution's answer<br/>with the official UGPhysics grader"]
    D --> E["Dataset v1.2<br/>29,500 short step-by-step solutions"]
    E --> F["LoRA on Qwen3.5-2B<br/>non-thinking, 12,000 examples,<br/>1 epoch on one T4"]
    F --> G["Apply the adapter at<br/>half strength and merge"]
    G --> H["Final test on<br/>unseen UGPhysics questions"]
```

1. **Data.** Physics problems with worked solutions from [MegaScience](https://huggingface.co/datasets/MegaScience/MegaScience) (textbook physics, NaturalReasoning physics, Nemotron-Science multiple choice, some maths) and the [PhysicsEval](https://huggingface.co/datasets/IUTVanguard/PhysicsEval) training split. Subjects are balanced toward what the exam asks and where the base model is weak. Every problem that overlaps a benchmark question is removed, and every solution whose final answer disagrees with its reference (official grader) is dropped.
2. **Training.** LoRA (rank 32) on attention, Gated DeltaNet and MLP layers of Qwen3.5-2B in its non-thinking chat format; the loss covers the answer only. fp16 with loss scaling, gradient checkpointing, and a chunked loss for the 248K-token vocabulary, so it fits a 15 GB T4.
3. **Half strength.** At full strength the answers became too short for hard problems: on 70 MATH-500 questions maths fell from 67.1% to 51.7%. Applying the adapter at 0.5× kept the physics gain and reduced the maths loss (69.4% on the same 70 questions, 63.5% vs 73.0% on 210).
4. **Evaluation.** A harness that reproduces the UGPhysics protocol, splits the benchmark into development questions (for every decision) and a held-out test (used once), and reports paired statistics.

Details: [docs/METHODS.md](docs/METHODS.md).

## What we learned

The model is the last of several experiments; the full story with every number is in [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md).

| # | Experiment | UGPhysics (dev) | Lesson |
|---|---|---|---|
| 1 | LFM2.5-1.2B-Thinking + short teacher solutions | 13.3% → 5.5% | Short solutions destroyed a thinking model's long reasoning. |
| 2 | LFM2.5-1.2B-Thinking + its own correct answers | 13.3% → 10.9% | Self-distillation kept the reasoning but added no physics skill. |
| 3 | Qwen3.5-2B (non-thinking) + short solutions, full strength | 14.5% → 16.6% | Fixed the rambling (52% → 2% hit the limit) but lost 15 points of maths. |
| 4 | Same adapter at half strength | 14.5% → **17.9%** | Kept the physics gain and reduced the maths loss. |
| 5 | Final test, held-out questions | 15.9% → **18.9%** | The gain is real on questions never used for any decision. |
| 6 | Four other small open models, same held-out questions | 5.0% – 15.9% | This model is first; reasoning distills run out of tokens on physics. |

## Repository layout

```
├── src/                  # the four tools (each one file, run from the notebooks)
│   ├── physeval.py       #   evaluation harness: UGPhysics, MATH-500, PhysicsEval; grading and reports
│   ├── physdata.py       #   training-data builder: filtering, leak checks, grader checks, subject quotas
│   ├── phystrain.py      #   LoRA/DoRA trainer for a free T4 (resumable, fp16, chunked loss)
│   └── physself.py       #   self-distillation data (experiment 2)
├── notebooks/            # Colab notebooks, one per stage (see notebooks/README.md)
├── results/              # evaluation reports, summary.json files, every generated answer (gzip)
│   └── compare/          #   the comparison with four other small models
├── training/             # training configs, loss logs and sampled answers
├── data/                 # dataset build reports and the v1.2 training data (gzip, CC BY-NC-SA 4.0)
├── tools/                # make_figures.py, make_compare_figure.py: the figures in this README
└── docs/                 # results, methods, experiment log, reproduction guide, model card, figures
```

## Reproduce

Everything runs in Google Colab on a free T4: copy `src/*.py` and `notebooks/*.ipynb` into one Google Drive folder (`MyDrive/physics_eval`) and run the notebooks in order. Step-by-step guide, GPU hours per step and how three free accounts were used in parallel: [docs/REPRODUCE.md](docs/REPRODUCE.md).

## Limitations

- About 4 of every 5 undergraduate physics problems are still answered wrongly. Do not rely on its answers without checking them.
- Weaker than the base model on hard maths (MATH-500 Level 5: 49% → 26%).
- About 7% of answers still run past 4,096 tokens.
- English only, text only (Qwen3.5-2B's image encoder is not included), evaluated only with greedy decoding.
- Compared with five open models (above). Qwen3-1.7B in thinking mode was not finished, and other small models (Gemma, SmolLM, Phi) were not tested, so no claim is made about them. The reasoning models were limited to 8,192 tokens.

## License

- **Code** (`src/`, `notebooks/`, `docs/`): [MIT](LICENSE).
- **Model weights** (on Hugging Face): CC BY-NC-SA 4.0. The base model Qwen3.5-2B is Apache-2.0.
- **Training data** (`data/`): derived from MegaScience (CC BY-NC-SA 4.0) and PhysicsEval (CC BY-SA 4.0), so it is shared under **CC BY-NC-SA 4.0**. See [data/README.md](data/README.md).
- **Benchmarks**: UGPhysics, MATH-500 and PhysicsEval belong to their authors. This repository stores model outputs, scores and the normalised reference answers used for grading, never the benchmark questions themselves.

## Citation

```bibtex
@misc{qwen35_2b_physics_2026,
  title  = {Qwen3.5-2B Physics: a physics fine-tune of Qwen3.5-2B trained on free Colab GPUs},
  author = {eswaroy},
  year   = {2026},
  url    = {https://github.com/eswaroy/qwen3.5-2b-physics}
}
```

## Acknowledgements

The [Qwen team](https://huggingface.co/Qwen) for Qwen3.5-2B; the authors of [UGPhysics](https://github.com/YangLabHKUST/UGPhysics) for the benchmark and its grader; the creators of [MegaScience](https://huggingface.co/datasets/MegaScience/MegaScience), [PhysicsEval](https://github.com/areebuzair/PhysicsEval) and [MATH-500](https://huggingface.co/datasets/HuggingFaceH4/MATH-500); and Google Colab for the free GPUs.
