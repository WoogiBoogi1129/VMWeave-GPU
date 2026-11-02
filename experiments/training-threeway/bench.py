#!/usr/bin/env python3
"""Identical completion-delimited FP32 training for all three execution paths."""
import argparse
import hashlib
import json
import math
import os
import resource
import time
from pathlib import Path

os.environ['DISABLE_ADDMM_CUDA_LT'] = '1'
os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
import torch

WIDTHS = {'small': (32, 64, 8), 'large': (2048, 4096, 1024)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', choices=WIDTHS, required=True)
    p.add_argument('--batch', type=int, choices=[32, 1024], required=True)
    p.add_argument('--input', choices=['resident', 'h2d', 'roundtrip'], required=True)
    p.add_argument('--steps', type=int, default=32)
    p.add_argument('--warmup', type=int, default=32)
    p.add_argument('--sync', type=int, default=16)
    p.add_argument('--device', choices=['cpu', 'cuda'], default='cuda')
    p.add_argument('--correctness', action='store_true')
    p.add_argument('--out', required=True)
    a = p.parse_args()
    assert a.steps > 0 and a.sync > 0 and a.steps % a.sync == 0
    assert not Path(a.out + '.json').exists()
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    torch.manual_seed(20261102)
    w = WIDTHS[a.model]
    model = torch.nn.Sequential(torch.nn.Linear(w[0], w[1]), torch.nn.ReLU(),
                                torch.nn.Linear(w[1], w[2])).float()
    initial = {k: v.detach().clone() for k, v in model.state_dict().items()}
    xc, yc = torch.randn(a.batch, w[0]), torch.randn(a.batch, w[2])
    fixture_hash = hashlib.sha256()
    for t in [*initial.values(), xc, yc]:
        fixture_hash.update(t.contiguous().numpy().tobytes())
    if a.device == 'cuda':
        assert torch.cuda.is_available() and torch.cuda.device_count() == 1
    model.to(a.device)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01, foreach=False, fused=False)
    x, y = xc.to(a.device), yc.to(a.device)
    cpu_output = torch.empty((a.batch, w[2]), dtype=torch.float32)

    def sync():
        if a.device == 'cuda':
            torch.cuda.synchronize()

    def step():
        if a.input != 'resident':
            x.copy_(xc, non_blocking=False)
            y.copy_(yc, non_blocking=False)
        optimizer.zero_grad(set_to_none=True)
        output = model(x)
        loss = torch.nn.functional.mse_loss(output, y)
        loss.backward()
        optimizer.step()
        if a.input == 'roundtrip':
            cpu_output.copy_(output.detach(), non_blocking=False)
        return loss, output

    metadata = dict(vars(a), widths=w, torch=str(torch.__version__), cuda=torch.version.cuda,
                    fixture_sha256=fixture_hash.hexdigest(),
                    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    affinity=sorted(os.sched_getaffinity(0)),
                    h2d_bytes_per_step=0 if a.input == 'resident' else 4*a.batch*(w[0]+w[2]),
                    d2h_bytes_per_step=4*a.batch*w[2] if a.input == 'roundtrip' else 0,
                    device_name=torch.cuda.get_device_name(0) if a.device == 'cuda' else 'cpu')
    if a.correctness:
        snapshots = {}
        for n in range(1, 11):
            loss, output = step()
            if n in [1, 10]:
                sync()
                snapshots[str(n)] = {
                    'loss': loss.detach().cpu().clone(),
                    'output': output.detach().cpu().clone(),
                    'weights': {k: v.detach().cpu().clone() for k, v in model.named_parameters()},
                    'gradients': {k: v.grad.detach().cpu().clone() for k, v in model.named_parameters()},
                }
                if a.input == 'roundtrip':
                    assert torch.equal(cpu_output, snapshots[str(n)]['output'])
        torch.save(snapshots, a.out + '.pt')
        metadata.update(correctness_snapshots=[1, 10], final_loss=float(snapshots['10']['loss']))
    else:
        for n in range(a.warmup):
            step()
            if (n+1) % a.sync == 0:
                sync()
        sync()
        model.load_state_dict(initial)
        optimizer.zero_grad(set_to_none=True)
        sync()
        cpu = lambda: resource.getrusage(resource.RUSAGE_SELF).ru_utime + resource.getrusage(resource.RUSAGE_SELF).ru_stime
        c0 = cpu()
        start_utc = time.time()
        print(json.dumps({'event': 'measurement_start', 'utc': start_utc}), flush=True)
        start = time.perf_counter()
        for n in range(a.steps):
            loss, output = step()
            if (n+1) % a.sync == 0:
                sync()
        sync()
        elapsed = time.perf_counter() - start
        end_utc = time.time()
        cpu_seconds = cpu() - c0
        metadata.update(start_utc=start_utc, end_utc=end_utc, elapsed_seconds=elapsed,
                        samples_per_second=a.steps*a.batch/elapsed,
                        step_seconds=elapsed/a.steps, guest_cpu_seconds=cpu_seconds,
                        final_loss=float(loss.detach().cpu()),
                        output_finite=bool(torch.isfinite(output.detach().cpu()).all()))
        if a.input == 'roundtrip':
            assert torch.equal(cpu_output, output.detach().cpu())
        assert metadata['output_finite']
    assert math.isfinite(metadata['final_loss'])
    metadata['completed'] = True
    Path(a.out + '.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps(metadata), flush=True)


if __name__ == '__main__':
    main()
