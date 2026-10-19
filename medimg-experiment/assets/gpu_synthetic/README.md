# Tiny real GPU protocol fixture

This example proves executable CUDA behavior on generated data only. It supplies no medical, clinical, external-generalization, or method-contribution evidence.

All images are generated in memory from fixed per-group RNG seeds. Each synthetic group contains one image: train/val/test have 12/4/4 disjoint fixed IDs. Inputs are 8×8 (2D) or 8×8×8 (3D), one channel. There is no patient data, dataset write, network request, pretrained model, or model-weight download.

`synth_data.py`, `torch_runtime.py`, `audit_split.py`, `evaluate_test.py`, `sampler.py`, and `validate_resume.py` must be frozen before candidate review. `model.py` and `train.py` are candidate code. Do not let direct fixture acceptance stand in for controller authorization or independent candidate review.

Candidate argv (substitute actual task/dimension literals):

```json
["{python}","train.py","--seed","{seed}","--task","classification","--dimension","2","--epochs","4"]
```

Whitelist flags: `--task`, `--dimension`, `--epochs`, `--width`, `--learning-rate`. Main metric is `accuracy` (classification) or mean per-group foreground `dice` (segmentation), direction maximize, statistic `mean_per_case`. Each saved case contains predictions and labels; case metrics and mean can be independently recomputed. Both `last` and `best` selection use the contract's `primary_metric.selection` field. Guard metrics are not supplied by this minimal fixture.

Audit argv:

```json
["{python}","audit_split.py","--task","classification","--dimension","2","--output","{output}"]
```

Locked test argv:

```json
["{python}","evaluate_test.py","--task","classification","--dimension","2","--run-dir","{run_dir}","--output","{output}"]
```

Trainer honors `ME_RUN_ID`, `ME_PHASE`, `ME_OUTPUT_DIR`, `ME_CONTRACT_PATH`, and `ME_DEVICE`. Requesting unavailable CUDA fails. `ME_TORCH_SITE`, when explicitly supplied, loads an approved compatible dependency directory in this process only. It never installs packages or changes a global environment. Use the interpreter required by the host's AGENTS.md.

`weights.pt` contains real selected weights and config. `checkpoint.pt` contains current/selected/initial model states, Adam moments and step counts, StepLR state, Python/NumPy/CPU/CUDA RNG, configuration, progress, metric history, and resume lineage. Supply a trusted compatible checkpoint through `ME_RESUME_PATH`; mismatch or an already complete checkpoint is rejected. Checkpoints use pickle and must come only from this trusted local fixture. Resumed outputs go to a new output directory. `ME_FIXTURE_INTERRUPT_AFTER_EPOCH=2` is explicit acceptance-only fault injection: the owned training process exits with code 75 after the durable checkpoint. The parent controller must record that failed run before scheduling a separate recovery segment.

`verify_run.py` reloads actual selected weights, reproduces exact val/test predictions and metrics, checks all registered group IDs, confirms optimized parameters and Adam counts, and can compare recovered final model/optimizer/scheduler/RNG/config to a fresh run.

Optional controller recovery declaration (both scripts must be frozen):

```json
{"recovery":{"checkpoint":"checkpoint.pt","validator_command":["{python}","validate_resume.py","{checkpoint}","{output}"],"timeout_seconds":30}}
```

The validator checks actual tensor keys/shapes/finite values and parameter changes, all Adam moments/counters, scheduler epochs/LRs, actual RNG state setters, progress/metric/selection consistency, and the frozen sampler implementation hash. `sampler.py` owns permutation generation and batching. Checkpoints exist only at completed epoch boundaries; their cursor is zero and their next permutation is reproducible from restored CUDA RNG. It rejects completed or incomplete-state checkpoints. Validation output includes the source run ID, seed, and exact checkpoint hash. A failed/incompatible checkpoint must lead to a separate rerun record rather than a claimed continuation.

Development acceptance: `tests/run_gpu_acceptance.py` (relative to the skill root) uses seeds 11/22/33 in all four task/dimension cells and verifies interrupted/resumed seed11 against a fresh seed11 for both last and best selection. The whole process has a maximum900-second cap (a lower `--budget-seconds` can be set) and each child a90-second cap. Its testing path constructs a locked test split solely to verify the frozen evaluator; these scores never select models or trigger revisions. Run it only after authorizing the real CUDA interpreter/dependency directory and output/budget; it is not invoked by ordinary unit tests or hosted CI.

An explicitly authorized bounded continuation can use `--supplement-from <original receipt directory>`. This development-recovery mode requires the original `source-before-validator-correction.json` provenance manifest and command receipts; it is not a generic resume option for arbitrary outputs. The entire continuation has an external90-second process-tree timeout and shares one torch import. It verifies source hashes and re-evaluates actual saved weights, group predictions/metrics and full state before recording reuse, and writes its verification evidence into new directories. Real interrupted training still uses separate owned subprocesses. A partial receipt lacking `acceptance.json` remains incomplete; a successful continuation must publish its own complete receipt and preserve the source partial evidence. Development corruption-rejection evidence was collected separately and is not automatically produced by this driver.
