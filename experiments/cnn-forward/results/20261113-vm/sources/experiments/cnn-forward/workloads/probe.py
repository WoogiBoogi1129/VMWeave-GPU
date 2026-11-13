"""CNN forward acceptance probe; CPU references never replace GPU execution."""
import argparse
import copy
import json
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--mode', choices=['cpu', 'gpu'], default='gpu')
parser.add_argument('--backend', choices=['legacy', 'default'], required=True)
parser.add_argument('--case', choices=['minimal', 'matrix', 'stream'], default='minimal')
parser.add_argument('--results', type=Path, default=Path('/results'))
args = parser.parse_args()
# Backend selection must happen before importing torch or initializing cuDNN.
if args.backend == 'legacy':
    os.environ['TORCH_CUDNN_V8_API_DISABLED'] = '1'
else:
    os.environ.pop('TORCH_CUDNN_V8_API_DISABLED', None)
assert os.environ.get('DISABLE_ADDMM_CUDA_LT') != '1'
import torch

args.results.mkdir(parents=True, exist_ok=True)
torch.set_num_threads(1)
torch.manual_seed(20261113)
torch.backends.cuda.matmul.allow_tf32 = False
torch.backends.cudnn.allow_tf32 = False
torch.backends.cudnn.benchmark = False
assert torch.backends.cudnn.enabled

def emit(stage, **fields):
    print(json.dumps(dict(stage=stage, **fields)), flush=True)

emit('environment', torch=torch.__version__, cuda=torch.version.cuda,
     mode=args.mode, backend=args.backend, case=args.case,
     rtol=1e-4, atol=1e-6, cudnn=torch.backends.cudnn.version())

if args.case == 'stream':
    # RTLD_DEFAULT resolves the Guest interposer. Do NOT call the native
    # libcudnn SetStream with an opaque remote handle (the old Nov 7 repro).
    assert args.mode == 'gpu'
    import ctypes
    lib = ctypes.CDLL(None)
    create, destroy = lib.cudnnCreate, lib.cudnnDestroy
    set_stream, get_stream = lib.cudnnSetStream, lib.cudnnGetStream
    create.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
    destroy.argtypes = [ctypes.c_void_p]
    set_stream.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    get_stream.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    for f in (create, destroy, set_stream, get_stream):
        f.restype = ctypes.c_int
    handle = ctypes.c_void_p()
    assert create(ctypes.byref(handle)) == 0
    try:
        explicit = torch.cuda.Stream()
        for stream in (torch.cuda.default_stream(), explicit):
            raw = stream.cuda_stream
            emit('set_stream_start', stream=raw)
            assert set_stream(handle, ctypes.c_void_p(raw)) == 0
            actual = ctypes.c_void_p()
            assert get_stream(handle, ctypes.byref(actual)) == 0
            assert (actual.value or 0) == raw
            emit('set_stream_done', stream=raw)
    finally:
        assert destroy(handle) == 0
    emit('PASS')
    raise SystemExit

configs = [(True, 1, 1, True)] if args.case == 'minimal' else [
    (bias, stride, padding, deterministic)
    for bias in (False, True) for stride in (1, 2) for padding in (0, 1)
    for deterministic in (True, False)
]
cpu_records, gpu_records, comparisons = {}, {}, []
for bias, stride, padding, deterministic in configs:
    torch.backends.cudnn.deterministic = deterministic
    label = f'b{int(bias)}-s{stride}-p{padding}-d{int(deterministic)}'
    model = torch.nn.Conv2d(3, 4, 3, stride=stride, padding=padding, bias=bias).train()
    data = torch.randn(2, 3, 8, 8)
    expected = model(data).detach()
    assert torch.isfinite(expected).all()
    # Independent CPU expression catches accidental probe shape/config errors.
    patches = torch.nn.functional.unfold(data, 3, padding=padding, stride=stride)
    manual = torch.matmul(model.weight.detach().reshape(4, -1), patches)
    if bias:
        manual += model.bias.detach().view(1, 4, 1)
    torch.testing.assert_close(expected, manual.reshape_as(expected), rtol=1e-4, atol=1e-6)
    cpu_records[label] = dict(input=data, state={k: v.detach().clone() for k, v in model.state_dict().items()}, output=expected)
    torch.save(cpu_records, args.results/'cpu.pt')
    emit('cpu_reference', config=label, output_shape=list(expected.shape))
    if args.mode == 'cpu':
        continue
    model = copy.deepcopy(model).cuda()
    inp = data.cuda().requires_grad_()
    torch.cuda.synchronize()
    for stream_name in ('default', 'explicit'):
        stream = torch.cuda.default_stream() if stream_name == 'default' else torch.cuda.Stream()
        for repeat in range(3):
            key = f'{label}/{stream_name}/{repeat}'
            with torch.cuda.stream(stream):
                emit('conv_forward_start', key=key)
                actual = model(inp)
                stream.synchronize()
                assert actual.is_cuda and actual.grad_fn is not None
                got = actual.detach().cpu()
                emit('conv_forward_done', key=key)
            gpu_records[key] = got
            ok = torch.allclose(got, expected, rtol=1e-4, atol=1e-6)
            comparisons.append(dict(key=key, passed=ok, max_abs=(got-expected).abs().max().item()))
            torch.save(gpu_records, args.results/'gpu.pt')
            (args.results/'comparison.json').write_text(json.dumps(comparisons, indent=2)+'\n')
            torch.testing.assert_close(got, expected, rtol=1e-4, atol=1e-6)
            del actual
    del model, inp
    torch.cuda.synchronize()
emit('PASS', configs=len(configs), gpu_comparisons=len(comparisons), backward_executed=False)
