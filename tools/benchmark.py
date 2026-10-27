"""Ordinary CUDA workload using installed PyTorch. Never tunes or resets a GPU."""
import argparse
import csv
import ctypes
import hashlib
import io
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

FIELDS = ('name', 'pci.bus_id', 'uuid', 'driver_version', 'vbios_version',
          'power.limit', 'clocks.max.sm', 'clocks.max.memory', 'temperature.gpu',
          'utilization.gpu', 'memory.used', 'power.draw', 'clocks.sm', 'clocks.mem')
MODES = ('fp32_pedantic', 'fp16_fp32_accumulate', 'bf16_fp32_accumulate',
         'tf32_fp32_accumulate', 'fp16_accumulate_control')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def snapshot():
    result = subprocess.run(['nvidia-smi', '--query-gpu=' + ','.join(FIELDS),
                             '--format=csv,noheader,nounits'], capture_output=True,
                            text=True, timeout=10, check=True)
    rows = list(csv.reader(io.StringIO(result.stdout.strip())))
    if len(rows) != 1 or len(rows[0]) != len(FIELDS):
        raise RuntimeError('Requires exactly one NVIDIA GPU and complete telemetry')
    row = dict(zip(FIELDS, (v.strip() for v in rows[0])))
    if row['name'] != 'NVIDIA GeForce RTX 3060 Ti' or row['pci.bus_id'].lower() != '00000000:02:00.0':
        raise RuntimeError('Wrong GPU or PCI address; refusing workload')
    for key in FIELDS[5:]:
        if not math.isfinite(float(row[key])):
            raise RuntimeError('Invalid telemetry: ' + key)
    row['utc'] = datetime.now(timezone.utc).isoformat()
    return row


def identity(row):
    return {key: row[key] for key in FIELDS[:8]}


def loaded_cuda_files():
    # Enumerate this process, not similarly named DLLs merely present on disk.
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.EnumProcessModules.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
    psapi.GetModuleFileNameExW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_ulong]
    handles = (ctypes.c_void_p * 4096)()
    needed = ctypes.c_ulong()
    process = kernel.GetCurrentProcess()
    if not psapi.EnumProcessModules(process, handles, ctypes.sizeof(handles), ctypes.byref(needed)) or needed.value > ctypes.sizeof(handles):
        raise RuntimeError('Cannot enumerate loaded runtime DLLs')
    files = []
    for handle in handles[:needed.value // ctypes.sizeof(ctypes.c_void_p)]:
        name = ctypes.create_unicode_buffer(32768)
        if psapi.GetModuleFileNameExW(process, handle, name, len(name)):
            path = Path(name.value)
            if path.name.lower().startswith(('cublas', 'cudart', 'torch_cuda', 'nvcuda', 'nvml')):
                files.append({'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path)})
    if not any('cublas' in Path(x['path']).name.lower() for x in files):
        raise RuntimeError('No loaded cuBLAS library found')
    return sorted(files, key=lambda x: x['path'].lower())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--runs', type=int, default=3, choices=[1, 3])
    parser.add_argument('--background-session', action='store_true',
                        help='Diagnostic only: permit idle desktop allocations up to 6GiB')
    args = parser.parse_args()
    if args.out.exists():
        raise RuntimeError('Use a new output directory; previous evidence is immutable')
    for name in ('NVIDIA_TF32_OVERRIDE', 'CUDA_VISIBLE_DEVICES'):
        if os.environ.get(name):
            raise RuntimeError('Refusing nonempty ' + name)
    before = snapshot()
    memory_limit = 6144 if args.background_session else 2048
    if float(before['utilization.gpu']) > 5 or float(before['temperature.gpu']) > 65 or float(before['memory.used']) > memory_limit:
        raise RuntimeError('GPU busy, warm, or insufficient free memory; close workloads, do not tune')
    args.out.mkdir(parents=True)

    def save(name, value):
        (args.out / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')

    import numpy as np
    import torch
    if torch.cuda.device_count() != 1 or torch.cuda.get_device_name(0) != before['name']:
        raise RuntimeError('CUDA target does not match the single NVIDIA GPU')
    torch.set_num_threads(4)
    torch.cuda.set_device(0)
    torch.backends.cuda.preferred_blas_library('cublas')
    matmul = torch.backends.cuda.matmul
    matmul.allow_fp16_reduced_precision_reduction = False
    matmul.allow_bf16_reduced_precision_reduction = False
    policy_names = ('allow_tf32', 'allow_fp16_reduced_precision_reduction',
                    'allow_bf16_reduced_precision_reduction', 'allow_fp16_accumulation')
    metadata = {'schema': 1, 'label': args.label, 'state_verified': False,
                'notes': 'Current benchmark session; unlock state requires separate evidence',
                'background_session': args.background_session,
                'eligible_for_clean_comparison': not args.background_session,
                'n': 4096, 'samples': 30, 'gemms_per_sample': 8, 'warmup_seconds': 2,
                'modes': MODES, 'torch': torch.__version__, 'cuda_build': torch.version.cuda,
                'torch_git': torch.version.git_version, 'python': sys.version,
                'python_executable_sha256': sha(sys.executable), 'runner_sha256': sha(__file__),
                'numpy': np.__version__, 'gpu_before': before, 'settings_changed': False,
                'precision_note': 'Requested PyTorch/cuBLAS policies, not instruction-level kernel proof'}
    save('context.json', metadata)
    telemetry, errors, phase = [], [], ['initialization']
    stop = threading.Event()

    def monitor():
        while not stop.is_set():
            try:
                row = snapshot()
                row['phase'] = phase[0]
                telemetry.append(row)
                if identity(row) != identity(before):
                    errors.append('GPU identity/driver/limit changed during measurement')
                if float(row['temperature.gpu']) >= 85:
                    errors.append('Temperature reached conservative 85C abort threshold')
            except Exception as error:
                errors.append(str(error))
            stop.wait(0.5)

    def guard():
        if errors:
            raise RuntimeError('; '.join(errors))

    worker = threading.Thread(target=monitor, daemon=True)
    worker.start()
    trials = []
    try:
        rng = np.random.default_rng(3060)
        # A separate small, nonuniform multiplication checks all output elements.
        small_a = rng.integers(-2, 3, (256, 256), dtype=np.int32).astype(np.float32)
        small_b = rng.integers(-2, 3, (256, 256), dtype=np.int32).astype(np.float32)
        small_reference = small_a.astype(np.float64) @ small_b.astype(np.float64)
        small_hashes = [hashlib.sha256(x.tobytes()).hexdigest() for x in (small_a, small_b)]
        for trial in range(1, args.runs + 1):
            results = []
            for mode in MODES:
                guard()
                phase[0] = f'trial-{trial}/{mode}'
                matmul.allow_tf32 = mode == 'tf32_fp32_accumulate'
                matmul.allow_fp16_accumulation = mode == 'fp16_accumulate_control'
                dtype = torch.bfloat16 if mode.startswith('bf16') else torch.float16 if mode.startswith('fp16') else torch.float32
                output_dtype = torch.float16 if mode.endswith('control') else torch.float32
                half_input = dtype in (torch.float16, torch.bfloat16)

                def multiply(a, b, out):
                    if half_input and output_dtype == torch.float32:
                        torch.mm(a, b, out_dtype=torch.float32, out=out)
                    else:
                        torch.mm(a, b, out=out)

                sa = torch.from_numpy(small_a).to(device='cuda', dtype=dtype)
                sb = torch.from_numpy(small_b).to(device='cuda', dtype=dtype)
                sc = torch.empty((256, 256), device='cuda', dtype=output_dtype)
                multiply(sa, sb, sc)
                small_result = sc.float().cpu().numpy()
                small_error = float(np.max(np.abs(small_result.astype(np.float64) - small_reference)))
                if not np.isfinite(small_result).all() or small_error != 0:
                    raise RuntimeError(f'Nonuniform numerical check failed: {mode}, error={small_error}')
                del sa, sb, sc
                n = 4096
                a = torch.ones((n, n), device='cuda', dtype=dtype)
                b = torch.ones_like(a)
                c = torch.empty((n, n), device='cuda', dtype=output_dtype)
                torch.cuda.synchronize()
                start_warmup = time.monotonic()
                while time.monotonic() - start_warmup < 2:
                    for _ in range(8):
                        multiply(a, b, c)
                    torch.cuda.synchronize()
                    guard()
                samples = []
                start, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
                for _ in range(30):
                    guard()
                    start.record()
                    for _ in range(8):
                        multiply(a, b, c)
                    end.record()
                    end.synchronize()
                    elapsed = start.elapsed_time(end) / 8
                    if not math.isfinite(elapsed) or elapsed <= 0:
                        raise RuntimeError('Invalid CUDA event timing')
                    samples.append(elapsed)
                output = c.cpu().numpy()
                tolerance = n * 0.01 if mode.endswith('control') else 0
                maximum_error = float(np.max(np.abs(output.astype(np.float32) - n)))
                if not np.isfinite(output).all() or maximum_error > tolerance:
                    raise RuntimeError(f'Full output validation failed: {mode}')
                median_ms = statistics.median(samples)
                result = {'mode': mode, 'samples_ms': samples, 'median_ms': median_ms,
                          'tflops': 2 * n ** 3 / (median_ms * 1e9),
                          'input_dtype': str(dtype), 'output_dtype': str(output_dtype),
                          'policy': {k: getattr(matmul, k) for k in policy_names},
                          'all_output_elements_checked': int(output.size),
                          'maximum_absolute_error': maximum_error, 'absolute_tolerance': tolerance,
                          'output_sha256': hashlib.sha256(output.tobytes()).hexdigest(),
                          'small_nonuniform_n': 256, 'small_input_sha256': small_hashes,
                          'small_maximum_absolute_error': small_error,
                          'small_output_sha256': hashlib.sha256(small_result.tobytes()).hexdigest()}
                results.append(result)
                print(f'trial {trial} {mode}: {result["tflops"]:.3f} TFLOPS; full output checked', flush=True)
                save(f'trial-{trial}-partial.json', results)
                del a, b, c, output
            save(f'trial-{trial}.json', results)
            trials.append(results)
        metadata['loaded_cuda_files'] = loaded_cuda_files()
        metadata['gpu_after'] = snapshot()
        if identity(metadata['gpu_after']) != identity(before):
            raise RuntimeError('GPU settings/identity changed')
        guard()
        save('context.json', metadata)
        summary = {mode: {'trial_tflops': [trial[i]['tflops'] for trial in trials],
                          'median_tflops': statistics.median(trial[i]['tflops'] for trial in trials)}
                   for i, mode in enumerate(MODES)}
        save('summary.json', summary)
    finally:
        stop.set()
        worker.join(timeout=12)
        save('telemetry.json', telemetry)
        save('monitor-errors.json', errors)
    guard()
    files = [args.out / 'context.json', args.out / 'summary.json', args.out / 'telemetry.json', args.out / 'monitor-errors.json']
    files += [args.out / f'trial-{i}.json' for i in range(1, args.runs + 1)]
    save('complete.json', {'completed': True, 'runs': args.runs,
                           'matched_comparison': False, 'unlock_state_proven': False,
                           'files': {x.name: sha(x) for x in files}})


if __name__ == '__main__':
    main()
