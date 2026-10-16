"""FP32 eager MLP training on CUDA, compared with identical CPU training."""
import os
os.environ['DISABLE_ADDMM_CUDA_LT'] = '1'
os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
import copy, json, time
import torch

torch.set_num_threads(1)
torch.manual_seed(20261016)
torch.use_deterministic_algorithms(True)
torch.backends.cuda.matmul.allow_tf32 = False
torch.backends.cudnn.allow_tf32 = False
assert torch.cuda.is_available() and torch.cuda.device_count() == 1
model = torch.nn.Sequential(torch.nn.Linear(32, 64), torch.nn.ReLU(), torch.nn.Linear(64, 8))
x = torch.randn(128, 32)
y = x[:, :8] * 0.5
initial = copy.deepcopy(model.state_dict())

def train(device):
    net = copy.deepcopy(model).to(device)
    a, b = x.to(device), y.to(device)
    opt = torch.optim.SGD(net.parameters(), lr=0.1, foreach=False, fused=False)
    losses = []
    start = time.monotonic()
    for step in range(100):
        opt.zero_grad(set_to_none=True)
        prediction = net(a)
        loss = torch.nn.functional.mse_loss(prediction, b)
        assert loss.device.type == device
        loss.backward()
        assert all(p.grad is not None and p.grad.device.type == device for p in net.parameters())
        opt.step()
        if device == 'cuda': torch.cuda.synchronize()
        losses.append(loss.detach().cpu().item())
        if step % 10 == 0 or step == 99:
            print(json.dumps({'event':'step', 'device':device, 'step':step+1, 'loss':losses[-1]}), flush=True)
    if device == 'cuda': torch.cuda.synchronize()
    params = {k:v.detach().cpu() for k,v in net.state_dict().items()}
    grads = {k:p.grad.detach().cpu() for k,p in net.named_parameters()}
    assert losses[-1] < losses[0] * 0.7, losses
    assert all(torch.isfinite(t).all() for t in [*params.values(), *grads.values()])
    assert any(not torch.equal(initial[k],v) for k,v in params.items())
    return params, grads, losses, time.monotonic()-start

cpu = train('cpu')
gpu = train('cuda')
for i in (0,1):
    for k in cpu[i]: torch.testing.assert_close(gpu[i][k], cpu[i][k], rtol=1e-4, atol=1e-6)
torch.testing.assert_close(torch.tensor(gpu[2]), torch.tensor(cpu[2]), rtol=1e-4, atol=1e-6)
result={'status':'PASS','torch':torch.__version__,'cuda':torch.version.cuda,'gpu':torch.cuda.get_device_name(0),
        'steps':100,'batch':128,'widths':[32,64,8],'optimizer':'SGD lr=0.1','loss':'MSE',
        'initial_loss':gpu[2][0],'final_loss':gpu[2][-1], 'training_seconds':gpu[3],
        'parameters_gradients_and_losses_match_cpu':True,'rtol':1e-4,'atol':1e-6,
        'max_parameter_abs_error':max((gpu[0][k]-cpu[0][k]).abs().max().item() for k in cpu[0])}
print(json.dumps({'event':'result',**result}),flush=True)
# Allow host to capture live channel and GPU PID evidence before GOODBYE.
input()
