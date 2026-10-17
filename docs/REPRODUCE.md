# Reproduce

[← back to README](../README.md)

Everything runs in Google Colab notebooks on a free **T4 GPU**. No paid service is needed. The original project used three free Google accounts (A, B, C) that share one Google Drive folder, so different steps could run at the same time.

## Setup

1. Create a folder in Google Drive: `MyDrive/physics_eval`. If you use several accounts, share it with them (Editor access) and add a shortcut to it in each account's `MyDrive`.
2. Copy **all files from [`src/`](../src) and [`notebooks/`](../notebooks)** into that one folder (the notebooks expect the `.py` files next to them).
3. Open a notebook from Drive in Colab and choose **Runtime > Change runtime type > T4 GPU**.

Every notebook saves its progress to Drive. After a Colab disconnect, run the notebook's first cells again, then the cell you were on: generation and training continue where they stopped. Never run the **same** run name on two accounts at the same time.

## Steps

| # | Notebook | What it does | GPU time (T4) |
|---|---|---|---|
| 1 | `PhysicsBaselineEval.ipynb` | Downloads the benchmarks, ranks the questions, scores the untouched base models | Qwen3.5-2B: about 5.6 h for 1,008 UGPhysics questions + 1.1 h for 210 MATH-500 |
| 2 | `PhysicsData.ipynb` | Builds the training data `v1.2` (filters, leak check, grader check) | mostly CPU; 20–40 min of streaming the first time |
| 3 | `PhysicsTrain.ipynb` §1–5 | Checks the data and format, then a 30-minute speed test | about 40 min |
| 4 | `PhysicsTrain.ipynb` §6 | Trains the LoRA adapter (647 steps) | about 4.5 h, over two sessions |
| 5 | `PhysicsTrain.ipynb` §9 | Evaluates checkpoints (9b), the bigger dev check (9c), the half-strength copy (9d) | 0.5–5 h each |
| 6 | `PhysicsFinalTest.ipynb` | Held-out test: base model and this model on 1,142 unseen questions, MATH-500 on 210 | about 6.3 h + 4.7 h + 1.5 h, on three accounts in parallel |
| 7 | `PhysicsPublish.ipynb` | Merges the adapter, checks the merge, writes the model card, uploads to Hugging Face | about 40 min |
| 8 | `PhysicsGitHub.ipynb` | Collects the results, logs and data from Drive and pushes this repository | no GPU |

`PhysicsSelf.ipynb` is only needed for experiment 2 (self-distillation of LFM2.5, see [EXPERIMENTS.md](EXPERIMENTS.md)).

### Settings used for the released model

In `PhysicsTrain.ipynb` section 1:

```python
MODEL = "Qwen/Qwen3.5-2B"
NO_THINKING = True
DATA = "v1.2"
PEFT = "lora"
RANK, ALPHA, DROPOUT = 32, 64, 0.0
LR = 1e-4
EPOCHS = 1
MAX_TRAIN = 12000
EXAMPLES_PER_STEP = 16
MAX_LEN = 2048
TOKENS_PER_MICRO = 8192
GRAD_CKPT = True
```

The released model is checkpoint `ckpt-00647` with `lora_alpha` set to 32 (section 9d makes this copy).

## Expected messages

- `causal_conv1d_fn ... falling back to its reference PyTorch implementation` and the same for `chunk_gated_delta_rule`: Qwen3.5's linear-attention layers run without optimized kernels. Correct, only slower.
- `skipped 5` or `6` at the start of training: the fp16 loss scale is being found. It should stop rising afterwards.
- `omegaconf ... requires antlr4-python3-runtime==4.9.*`: harmless; the UGPhysics grader needs version 4.11.1.
- Colab's preinstalled `torchao` breaks new PEFT versions; the notebooks uninstall it.

## Checking your numbers

Small differences from the reported numbers are normal: GPU kernels and library versions change greedy outputs slightly. Compare runs with the paired head-to-head table in each report rather than with single accuracy numbers.
