# Benchmark Protocol

The published comparison uses the two fresh 28 October 2026 sessions, not an
estimated baseline. Both used the same measured runner and loaded DLL hashes.

- PyTorch 2.11.0+cu128, NumPy 2.5.2 and Windows NVIDIA driver 617.42.
- Dense 4096 x 4096 matrix multiplication; five modes; three trials per state.
- Two-second warmup per mode, 30 CUDA-event samples, eight GEMMs per sample.
- Median of each trial's samples, then the median of the three trials.
- FP16/BF16 reductions disabled; FP16 accumulation allowed only for its control.
  Non-control FP16/BF16 explicitly request FP32 output. TF32 allowed only in
  its named mode. These are API policies, not disassembled-kernel proof.
- Every timed output element checked against the all-ones product. A separate
  deterministic 256-square integer-input test checks all outputs against CPU
  FP64. Both states produced matching full-output and smoke-test hashes.
- GPU telemetry sampled throughout; no benchmark-applied clock, voltage,
  power-limit, driver, firmware or boot-order changes.

PyTorch warned that preferred-BLAS selection is unsupported on Windows. The
actual loaded cuBLAS/cuBLASLt/runtime/driver modules were identified and hashed;
the guide does not infer a specific kernel from that selection request.

## Run It Yourself

The supplied [benchmark.py](tools/benchmark.py) is a measurement tool, not an
unlocker. It deliberately requires one RTX 3060 Ti at PCI `00000000:02:00.0`.
It refuses another target; an agent must review target selection for another PC.
Use an existing compatible CUDA-enabled PyTorch environment with NumPy.

From this repository in PowerShell, replace the Python path with that environment:

```powershell
$python = "C:\path\to\venv\Scripts\python.exe"
$out = ".\local-runs\locked-$(Get-Date -Format yyyyMMdd-HHmmss)"
& $python -I .\tools\benchmark.py --out $out --label locked --runs 3
```

Run in a new output folder for each state. Use `--label unlocked` only for the
intended unlocked session. Keep the same environment, display arrangement and
settings; do not benchmark while another GPU workload runs. A nonempty
`NVIDIA_TF32_OVERRIDE` or `CUDA_VISIBLE_DEVICES` is refused. Normal preflight
requires <=5% GPU usage, <=65 C and <=2048 MiB already allocated. A monitored
85 C threshold aborts between GPU batches. Do not repeatedly retry a failure.

`complete.json` is written only after successful trials, numerical checks,
telemetry and provenance capture. `summary.json` contains the scores.
Outputs under ignored `local-runs/` contain private device IDs and local DLL
paths: sanitize them before sharing. Hashes detect edits, not signed attestation.

The published runner differs from the measured source only in one generic
metadata note. Workload code is unchanged; both source hashes are recorded in
[provenance.json](results/provenance.json). Do not manufacture a completed run
or claim the newly published file's hash was used for the historical trials.

## Limits

The locked session used two monitors on the RTX; the unlocked session used
one RTX monitor and one iGPU monitor. This is an observed same-machine
comparison, not a perfectly controlled display-layout experiment. No complete
AI application, game, sleep/resume or long-term stability test was run.
