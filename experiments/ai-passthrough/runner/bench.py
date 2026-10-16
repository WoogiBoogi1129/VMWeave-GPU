#!/usr/bin/env python3
"""Identical FP32 training workload; no CPU fallback or per-step synchronization."""
import argparse, hashlib, json, os, resource, time
from pathlib import Path
os.environ['DISABLE_ADDMM_CUDA_LT']='1'
os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
import torch
p=argparse.ArgumentParser();p.add_argument('--model',choices=['small','medium','large'],required=True);p.add_argument('--batch',type=int,default=32);p.add_argument('--input',choices=['resident','transfer'],default='resident');p.add_argument('--mode',choices=['fixture','correctness','performance'],required=True);p.add_argument('--fixture',required=True);p.add_argument('--out',required=True);p.add_argument('--seconds',type=float,default=120);p.add_argument('--warmup',type=float,default=30);a=p.parse_args()
torch.set_num_threads(1);torch.use_deterministic_algorithms(True);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.benchmark=False
torch.manual_seed(20261016)
w={'small':[32,64,8],'medium':[1024,2048,512],'large':[2048,4096,1024]}[a.model]
def model():return torch.nn.Sequential(torch.nn.Linear(w[0],w[1]),torch.nn.ReLU(),torch.nn.Linear(w[1],w[2])).float()
if a.mode=='fixture':
 assert not Path(a.fixture).exists()
 m=model();torch.save({'weights':m.state_dict(),'x':torch.randn(1024,w[0]),'y':torch.randn(1024,w[2])},a.fixture);raise SystemExit
assert torch.cuda.is_available() and torch.cuda.device_count()==1,'Exactly one CUDA device required'
f=torch.load(a.fixture,map_location='cpu',weights_only=True);m=model().cuda();m.load_state_dict(f['weights']);o=torch.optim.SGD(m.parameters(),lr=0.01,foreach=False,fused=False)
xc,yc=f['x'][:a.batch],f['y'][:a.batch]
if a.input=='resident':x,y=xc.cuda(),yc.cuda()
def step():
 global x,y
 if a.input=='transfer':x,y=xc.cuda(),yc.cuda()
 o.zero_grad(set_to_none=True);loss=torch.nn.functional.mse_loss(m(x),y);loss.backward();o.step();return loss
meta={'model':a.model,'widths':w,'batch':a.batch,'input':a.input,'mode':a.mode,'torch':str(torch.__version__),'cuda':torch.version.cuda,'device':torch.cuda.get_device_name(0),'fixture_sha256':hashlib.sha256(Path(a.fixture).read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'affinity':sorted(os.sched_getaffinity(0))}
if a.mode=='correctness':
 states={}
 for i in range(100):
  loss=step()
  if i+1 in [1,10,100]:
   torch.cuda.synchronize();states[str(i+1)]={'loss':loss.detach().cpu(),'weights':{k:v.detach().cpu().clone() for k,v in m.named_parameters()},'gradients':{k:v.grad.detach().cpu().clone() for k,v in m.named_parameters()}}
 torch.save(states,a.out+'.pt');meta.update(loss=float(states['100']['loss']),finite=all(torch.isfinite(t).all().item() for c in states.values() for d in [c['weights'],c['gradients']] for t in d.values()))
else:
 # Warmup uses coarse completion-delimited batches; performance has only boundary syncs.
 t=time.monotonic();warmsteps=0
 while time.monotonic()-t<a.warmup:
  for _ in range(20):step();warmsteps+=1
  torch.cuda.synchronize()
 warmelapsed=time.monotonic()-t
 m.load_state_dict(f['weights']);o.zero_grad(set_to_none=True);torch.cuda.synchronize()
 cpu=lambda:resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime
 start=time.monotonic();wall=time.time();c0=cpu();n=0
 print(json.dumps({'event':'measurement_start','utc':wall}),flush=True)
 while time.monotonic()-start<a.seconds:loss=step();n+=1
 torch.cuda.synchronize();elapsed=time.monotonic()-start;c1=cpu()
 meta.update(start_utc=wall,end_utc=time.time(),steps=n,elapsed_seconds=elapsed,samples_per_second=n*a.batch/elapsed,guest_cpu_seconds=c1-c0,warmup_seconds=warmelapsed,warmup_steps=warmsteps)
 torch.cuda.synchronize();meta['final_loss']=float(loss.detach().cpu());assert __import__('math').isfinite(meta['final_loss']), 'Nonfinite final loss'
Path(a.out+'.json').write_text(json.dumps(meta,indent=2));print(json.dumps(meta),flush=True)
