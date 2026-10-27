# Performance Benchmark Comparison

## 3060 TI unlock

Measured Windows results, 28 October 2026: the affected FP16/BF16 tensor paths
were approximately **1.9x** as fast following a board-specific UEFI unlock.

| Arithmetic | Locked TFLOPS | Unlocked TFLOPS | Change |
| --- | ---: | ---: | ---: |
| FP32 control | 9.23 | 9.21 | -0.1% |
| FP16, FP32 accumulation | 27.18 | 51.54 | +89.6% |
| BF16, FP32 accumulation | 27.05 | 51.26 | +89.5% |
| TF32 | 13.67 | 26.38 | +93.0% |
| Full-rate FP16 control | 54.31 | 55.01 | +1.3% |

Three trials per state; median of medians. Same physical GPU, driver, measured
benchmark source, loaded library hashes and recorded 200 W limit. FP32 and the
full-rate FP16 control remained close. [Raw trials and results](results/).

**Limit:** the locked run used two RTX-connected monitors; the unlocked run
used one RTX monitor and one iGPU monitor. This is an observed same-machine
comparison, not a perfectly controlled display-layout experiment. These are
dense matrix benchmarks, not measured whole-application AI or gaming gains.

### Tested System

- RTX 3060 Ti LHR, GA104, 8 GiB; PCI `10de:2489`, subsystem `10de:153c`.
- VBIOS `94.04.6b.00.03`, unchanged; Windows NVIDIA driver `617.42`.
- Core Ultra 7 265K, MSI PRO Z890-P WIFI, Intel iGPU recovery display.
- PyTorch `2.11.0+cu128`, CUDA build `12.8`; [exact protocol](BENCHMARK.md).

### Process And Verification

Read-only discovery established the exact board, PCI location, live PROM and
display routing. Local profile/packaging and bounded ROM parsing changes were
validated with regression and native host tests. Release-only and reset/recovery
checks preceded the manually confirmed full UEFI transaction.

The successful repeated run passed all 35 firmware checkpoints: selectors
`SS0=0x88888888 / SS1=0x8` survived one FLR, DMA maps were released, bus mastering
was off and cleanup passed. Windows then started directly without a system
reboot. Firmware evidence and Windows throughput are separate checks.
[Firmware excerpt](evidence/uefi-result.txt) and [hash provenance](results/provenance.json).

### Two Guides

1. **[Human guide](HUMAN-GUIDE.md):** an agent prompt, USB preparation, monitor
   connection, one-time boot, manual confirmation, recovery and benchmarking.
2. **[Agent guide](AGENT-GUIDE.md):** source repositories, supporting files,
   read-only machine discovery, exact profiles, staged testing and validation.

**Scope and safety:** this is a volatile, machine-specific experiment, not a
VBIOS flash or a generic 3060 Ti installer. An independently driven, powered-on
display is required by the tested build during UEFI operations. An early missing-
display refusal must not be bypassed. No EFI image, private host profile, VBIOS,
Windows bootloader or vendor firmware is distributed here.

### Sources And Prior Art

- [UEFI base](https://github.com/yuksew/gpu-unlock-uefi)
- [Upstream unlock](https://github.com/Zagitta/gpu-unlock)
- [Other Windows port](https://github.com/impacifist/Windows-GPU-UNLOCK)
- [Earlier 3060 Ti Linux result](https://github.com/Zagitta/gpu-unlock/issues/177)

This is a Windows case report.
Original repository material is [MIT-licensed](LICENSE); referenced projects
and vendor files retain their own licenses. Long-term stability is untested.
