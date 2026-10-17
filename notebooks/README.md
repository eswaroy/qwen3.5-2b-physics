# Notebooks

Run them in Google Colab on a T4 GPU, with every notebook and every file from [`../src`](../src) in one Google Drive folder (`MyDrive/physics_eval`). Full guide: [docs/REPRODUCE.md](../docs/REPRODUCE.md).

| Order | Notebook | Purpose |
|---|---|---|
| 1 | [`PhysicsBaselineEval.ipynb`](PhysicsBaselineEval.ipynb) | Prepare the benchmarks and score the untouched base models |
| 2 | [`PhysicsData.ipynb`](PhysicsData.ipynb) | Build the training data (v1.2) |
| – | [`PhysicsSelf.ipynb`](PhysicsSelf.ipynb) | Self-distillation data (experiment 2 only) |
| 3 | [`PhysicsTrain.ipynb`](PhysicsTrain.ipynb) | Check, speed test, train, evaluate checkpoints, make the half-strength adapter |
| 4 | [`PhysicsFinalTest.ipynb`](PhysicsFinalTest.ipynb) | Held-out final test and the bigger MATH-500 check |
| 5 | [`PhysicsPublish.ipynb`](PhysicsPublish.ipynb) | Merge, check, write the model card, upload to Hugging Face |
| 6 | [`PhysicsGitHub.ipynb`](PhysicsGitHub.ipynb) | Collect results, logs and data, and push this repository |
