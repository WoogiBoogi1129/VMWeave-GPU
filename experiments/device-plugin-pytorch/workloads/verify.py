#!/usr/bin/env python3
"""Functional validation only; no throughput measurements or CPU fallback."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback

p = argparse.ArgumentParser()
p.add_argument('--mode', choices=['cpu', 'gpu', 'hold'], required=True)
p.add_argument('--profile', choices=['default', 'compat'], default='default')
p.add_argument('--hold-seconds', type=int, default=0)
p.add_argument('--results', default='/results')
a = p.parse_args()
assert 0 <= a.hold_seconds <= 120
if a.profile == 'compat':
    os.environ['DISABLE_ADDMM_CUDA_LT'] = '1'
os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
result_dir = Path(a.results)
result_dir.mkdir(parents=True, exist_ok=True)
stage = 'import'
events = []

def emit(event, **values):
    row = dict(event=event, utc=time.time(), mode=a.mode, profile=a.profile, **values)
    events.append(row)
    print(json.dumps(row), flush=True)
    tmp = result_dir / 'status.tmp'
    tmp.write_text(json.dumps(events, indent=2) + '\n')
    tmp.replace(result_dir / 'status.json')

def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(4*1024*1024), b''): h.update(b)
    return h.hexdigest()

try:
    emit('stage', stage=stage)
    import torch
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    torch.manual_seed(20261106)
    torch_path = Path(torch.__file__).parent
    paths = [Path(torch.__file__), Path(torch._C.__file__), torch_path/'version.py',
             torch_path/'lib/libtorch_cuda.so', torch_path/'lib/libc10_cuda.so']
    hashes = {str(f): digest(f) for f in paths if f.exists()}
    emit('identity', torch=str(torch.__version__), cuda=torch.version.cuda,
         python=sys.version, torchPath=str(torch_path), uid=os.getuid(),
         groups=os.getgroups(), files=hashes, sourceSHA256=digest(__file__))
    stage = 'cpu-reference'
    emit('stage', stage=stage)
    x = torch.arange(12, dtype=torch.float32).reshape(3, 4) / 8
    y = torch.arange(8, dtype=torch.float32).reshape(4, 2) / 16
    reference = x @ y
    assert bool(torch.isfinite(reference).all())
    emit('cpu-pass', result=reference.tolist())
    if a.mode == 'cpu':
        emit('PASS', scope='official image import and CPU reference only')
        sys.exit(0)
    stage = 'cuda-initialization'
    emit('stage', stage=stage)
    available = torch.cuda.is_available()
    count = torch.cuda.device_count()
    emit('cuda-discovery', available=available, count=count)
    # init provides the actual error even when is_available() returned False.
    torch.cuda.init()
    assert available and count == 1
    emit('cuda-initialized', name=torch.cuda.get_device_name(0))
    stage = 'gpu-operations'
    emit('stage', stage=stage)
    gx, gy = x.to('cuda'), y.to('cuda')
    assert gx.is_cuda and gy.is_cuda
    torch.cuda.synchronize()
    torch.testing.assert_close(gx.cpu(), x, rtol=0, atol=0)
    torch.testing.assert_close((gx + gx).cpu(), x + x, rtol=1e-4, atol=1e-6)
    answer = gx @ gy
    torch.cuda.synchronize()
    torch.testing.assert_close(answer.cpu(), reference, rtol=1e-4, atol=1e-6)
    emit('gpu-operations-pass', device=str(answer.device), result=answer.cpu().tolist())
    if a.mode != 'hold':
        stage = 'training'
        emit('stage', stage=stage)
        torch.manual_seed(20261106)
        cpu_model = torch.nn.Sequential(torch.nn.Linear(32,64), torch.nn.ReLU(), torch.nn.Linear(64,8)).float()
        gpu_model = copy.deepcopy(cpu_model).to('cuda')
        initial = {k:v.detach().clone() for k,v in cpu_model.named_parameters()}
        tx, ty = torch.randn(32,32), torch.randn(32,8)
        gtx, gty = tx.to('cuda'), ty.to('cuda')
        options = dict(foreach=False, fused=False) if a.profile == 'compat' else {}
        co = torch.optim.SGD(cpu_model.parameters(), lr=0.01, **options)
        go = torch.optim.SGD(gpu_model.parameters(), lr=0.01, **options)
        snapshots, metrics = {}, []
        for step in range(1,6):
            def advance(model, optimizer, inputs, targets):
                optimizer.zero_grad(set_to_none=True)
                output=model(inputs);loss=torch.nn.functional.mse_loss(output,targets)
                loss.backward();optimizer.step()
                return dict(loss=loss.detach().cpu(), output=output.detach().cpu(),
                            **{'weight/'+n:t.detach().cpu().clone() for n,t in model.named_parameters()},
                            **{'gradient/'+n:t.grad.detach().cpu().clone() for n,t in model.named_parameters()})
            cr=advance(cpu_model,co,tx,ty)
            gr=advance(gpu_model,go,gtx,gty)
            torch.cuda.synchronize()
            for collection in [cr,gr]:
                assert all(bool(torch.isfinite(t).all()) for t in collection.values())
            if step in [1,5]:
                for name in cr:
                    torch.testing.assert_close(gr[name],cr[name],rtol=1e-4,atol=1e-6)
                    metrics.append(dict(step=step,tensor=name,shape=list(cr[name].shape),
                                        maxAbsError=float((gr[name].double()-cr[name].double()).abs().max())))
                snapshots[str(step)]={'cpu':cr,'gpu':gr}
            emit('training-step-pass', step=step, loss=float(gr['loss']))
        changed=any(not torch.equal(initial[n],t.detach().cpu()) for n,t in gpu_model.named_parameters())
        assert changed
        torch.save(snapshots,result_dir/'snapshots.pt')
        emit('training-pass',steps=5,parametersChanged=changed,rtol=1e-4,atol=1e-6,comparisons=metrics)
    if a.hold_seconds:
        emit('holding', seconds=a.hold_seconds, pid=os.getpid())
        time.sleep(a.hold_seconds)
    torch.cuda.synchronize()
    emit('PASS',scope='official PyTorch GPU functional validation')
except Exception as exc:
    emit('FAIL',stage=stage,errorType=type(exc).__name__,error=str(exc))
    traceback.print_exc()
    sys.exit(1)
