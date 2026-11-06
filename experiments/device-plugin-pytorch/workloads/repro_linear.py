#!/usr/bin/env python3
"""Isolate the first Linear forward; no optimizer, training, or benchmark."""
import argparse
import faulthandler
import hashlib
import json
import os

faulthandler.enable(all_threads=True)
p = argparse.ArgumentParser()
p.add_argument('--disable-lt', action='store_true')
a = p.parse_args()
if a.disable_lt:
    os.environ['DISABLE_ADDMM_CUDA_LT'] = '1'
os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
import torch

torch.set_num_threads(1)
torch.backends.cuda.matmul.allow_tf32 = False
torch.manual_seed(20261106)
model = torch.nn.Linear(32, 64).float()
x = torch.arange(1024, dtype=torch.float32).reshape(32, 32) / 1024
reference = model(x).detach()
model = model.to('cuda')
x = x.to('cuda')
print(json.dumps({'event': 'before-linear', 'disableLT': a.disable_lt,
                  'torch': str(torch.__version__), 'cuda': torch.version.cuda,
                  'sourceSHA256': hashlib.sha256(open(__file__, 'rb').read()).hexdigest()}), flush=True)
answer = model(x)
torch.cuda.synchronize()
torch.testing.assert_close(answer.cpu(), reference, rtol=1e-4, atol=1e-6)
print(json.dumps({'event': 'PASS', 'disableLT': a.disable_lt,
                  'maxAbsError': float((answer.cpu()-reference).abs().max())}), flush=True)
