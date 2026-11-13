#!/usr/bin/env python3
"""Bounded CNN diagnosis; CPU is a reference, never a GPU fallback."""
import argparse
import copy
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

os.environ['TORCH_CUDNN_V8_API_DISABLED'] = '1'
os.environ['DISABLE_ADDMM_CUDA_LT'] = '1'
os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
p = argparse.ArgumentParser()
p.add_argument('--mode', choices=['cpu', 'gpu'], required=True)
p.add_argument('--case', choices=['basic', 'conv-forward', 'conv-train', 'conv-bn', 'all', 'cudnn-stream'], required=True)
a = p.parse_args()
OUT = Path('/results'); OUT.mkdir(exist_ok=True)
stage = 'import'

def emit(event, **values):
    print(json.dumps(dict(event=event, stage=stage, mode=a.mode, case=a.case, **values)), flush=True)

def maps(label):
    lines = Path('/proc/self/maps').read_text().splitlines()
    paths = sorted({s.split()[-1] for s in lines if any(x in s for x in ['cudnn', 'cublas', 'libcuda', 'vmweave', 'libtorch'])})
    emit('loaded-libraries', label=label, paths=paths)

def symbols():
    class Info(ctypes.Structure):
        _fields_ = [('fname', ctypes.c_char_p), ('base', ctypes.c_void_p), ('sname', ctypes.c_char_p), ('addr', ctypes.c_void_p)]
    dl = ctypes.CDLL(None)
    dl.dladdr.argtypes = [ctypes.c_void_p, ctypes.POINTER(Info)]; dl.dladdr.restype = ctypes.c_int
    for scope, lib in [('global', dl), ('native-cudnn', ctypes.CDLL('libcudnn.so.9', mode=os.RTLD_NOLOAD | os.RTLD_LAZY))]:
        for name in ['cudnnCreate', 'cudnnSetStream', 'cudnnCreateTensorDescriptor', 'cudnnSetTensorNdDescriptor', 'cudnnCreateFilterDescriptor', 'cudnnCreateConvolutionDescriptor', 'cudnnConvolutionForward', 'cudnnConvolutionBackwardData', 'cudnnConvolutionBackwardFilter', 'cudnnBatchNormalizationForwardTrainingEx', 'cudnnBackendExecute']:
            try:
                fn = getattr(lib, name); info = Info(); dl.dladdr(ctypes.cast(fn, ctypes.c_void_p), ctypes.byref(info))
                emit('symbol', scope=scope, symbol=name, library=info.fname.decode() if info.fname else None)
            except AttributeError:
                emit('symbol', scope=scope, symbol=name, library=None)

try:
    emit('stage')
    import torch
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)
    emit('identity', torch=str(torch.__version__), cuda=torch.version.cuda,
         cudnn=torch.backends.cudnn.version(), python=sys.version,
         sourceSHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
         settings={k: os.environ.get(k) for k in ['TORCH_CUDNN_V8_API_DISABLED', 'DISABLE_ADDMM_CUDA_LT', 'VMWEAVE_MIRROR_DEVICE_VA']},
         rtol=1e-4, atol=1e-6)
    maps('after-import')

    def fixture(case):
        torch.manual_seed(20261107)
        conv = torch.nn.Conv2d(3, 4, 3, padding=1, bias=True)
        model = torch.nn.Sequential(conv, torch.nn.BatchNorm2d(4), torch.nn.ReLU()) if case == 'conv-bn' else conv
        return model.float(), torch.randn(2, 3, 8, 8), torch.randn(2, 4, 8, 8)

    def advance(model, x, target, train, device):
        global stage
        model.train(); optimizer = torch.optim.SGD(model.parameters(), lr=0.01, foreach=False, fused=False)
        saved = {}
        for step in range(1, (3 if train else 1) + 1):
            optimizer.zero_grad(set_to_none=True); x.grad = None
            stage = f'{device}-forward-{step}'; emit('stage'); maps('before-forward')
            output = model(x)
            if device == 'cuda': torch.cuda.synchronize()
            emit('forward-complete', shape=list(output.shape), device=str(output.device))
            loss = torch.nn.functional.mse_loss(output, target)
            if train:
                stage = f'{device}-backward-{step}'; emit('stage'); loss.backward()
                if device == 'cuda': torch.cuda.synchronize()
                assert x.grad is not None
                assert all(t.grad is not None for t in model.parameters())
                emit('backward-complete')
                stage = f'{device}-optimizer-{step}'; emit('stage'); optimizer.step()
                if device == 'cuda': torch.cuda.synchronize()
            row = {'output': output.detach().cpu().clone(), 'loss': loss.detach().cpu().clone()}
            row.update({'state/'+n: t.detach().cpu().clone() for n,t in model.state_dict().items()})
            if train:
                row['input-gradient'] = x.grad.detach().cpu().clone()
                row.update({'gradient/'+n: t.grad.detach().cpu().clone() for n,t in model.named_parameters()})
            assert all(bool(torch.isfinite(t).all()) for t in row.values())
            saved[str(step)] = row
        return saved

    if a.mode == 'gpu':
        stage = 'cuda-basic'; emit('stage')
        torch.cuda.init(); assert torch.cuda.device_count() == 1
        x = torch.arange(12, dtype=torch.float32).reshape(3, 4) / 8
        y = torch.arange(8, dtype=torch.float32).reshape(4, 2) / 16
        gx, gy = x.cuda(), y.cuda()
        torch.testing.assert_close((gx @ gy).cpu(), x @ y, rtol=1e-4, atol=1e-6)
        torch.testing.assert_close((gx + gx).cpu(), x + x, rtol=0, atol=0)
        torch.cuda.synchronize(); emit('cuda-basic-pass', device=torch.cuda.get_device_name(0))
        symbols()
        if a.case == 'cudnn-stream':
            stage = 'direct-cudnn-create'; emit('stage')
            lib = ctypes.CDLL(None); handle = ctypes.c_void_p()
            lib.cudnnCreate.argtypes = [ctypes.POINTER(ctypes.c_void_p)]; lib.cudnnCreate.restype = ctypes.c_int
            rc = lib.cudnnCreate(ctypes.byref(handle)); emit('api-return', api='cudnnCreate', status=rc); assert rc == 0
            stage = 'direct-cudnn-setstream'; emit('stage')
            # This explicit native lookup reproduces libtorch_cuda's observed
            # binding, not CDLL(None)'s different global lookup scope.
            native = ctypes.CDLL('libcudnn.so.9', mode=os.RTLD_NOLOAD | os.RTLD_LAZY)
            native.cudnnSetStream.argtypes = [ctypes.c_void_p, ctypes.c_void_p]; native.cudnnSetStream.restype = ctypes.c_int
            rc = native.cudnnSetStream(handle, None); emit('api-return', api='cudnnSetStream', status=rc); assert rc == 0
            lib.cudnnDestroy.argtypes = [ctypes.c_void_p]; lib.cudnnDestroy.restype = ctypes.c_int
            assert lib.cudnnDestroy(handle) == 0
    cases = ['conv-forward', 'conv-train', 'conv-bn'] if a.case == 'all' else ([a.case] if a.case.startswith('conv-') else [])
    for case in cases:
        cm, x, target = fixture(case); initial = {n:t.detach().clone() for n,t in cm.named_parameters()}
        gm = copy.deepcopy(cm) if a.mode == 'gpu' else None
        reference = advance(cm, x.clone().requires_grad_(True), target, case != 'conv-forward', 'cpu')
        torch.save(reference, OUT / (case+'-cpu.pt')); emit('cpu-reference-pass', fixture=case, steps=len(reference))
        if case != 'conv-forward': assert any(not torch.equal(initial[n], t) for n,t in cm.named_parameters())
        if gm is not None:
            stage = 'cuda-transfer'; emit('stage')
            gm = gm.cuda(); xx = x.cuda().requires_grad_(True); yy = target.cuda(); torch.cuda.synchronize()
            actual = advance(gm, xx, yy, case != 'conv-forward', 'cuda')
            torch.save(actual, OUT / (case+'-gpu.pt'))
            metrics = []
            for step, tensors in reference.items():
                for name, expected in tensors.items():
                    actual_t = actual[step][name]
                    torch.testing.assert_close(actual_t, expected, rtol=1e-4, atol=1e-6)
                    metrics.append(dict(step=step, tensor=name, maxAbsError=float((actual_t.double()-expected.double()).abs().max())))
            emit('comparison-pass', comparisons=metrics)
    stage = 'complete'; emit('PASS', scope='functional diagnosis only')
except Exception as exc:
    emit('FAIL', errorType=type(exc).__name__, error=str(exc)); maps('failure')
    traceback.print_exc(); sys.exit(1)
