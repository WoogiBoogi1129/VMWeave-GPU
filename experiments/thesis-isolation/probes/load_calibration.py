"""Fixed eager FP32 MLP inference; serial submissions, no CPU fallback."""
import os,time,json,sys,signal
os.environ['DISABLE_ADDMM_CUDA_LT']='1'
os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
import torch
import numpy as np
torch.set_num_threads(1)
torch.manual_seed(20261012)
torch.use_deterministic_algorithms(True)
torch.backends.cuda.matmul.allow_tf32=False
torch.backends.cudnn.allow_tf32=False
assert torch.cuda.is_available() and torch.cuda.device_count()==1
net=torch.nn.Sequential(torch.nn.Linear(1024,2048),torch.nn.ReLU(),torch.nn.Linear(2048,1024)).float().eval()
x=torch.randn(32,1024)
with torch.no_grad():reference=net(x).numpy().copy()
net=net.cuda();x=x.cuda()
def request():
 with torch.no_grad():
  started=time.monotonic();y=net(x);torch.cuda.synchronize();latency=time.monotonic()-started
  actual=y.cpu().numpy()
 return latency,bool(np.allclose(actual,reference,rtol=1e-4,atol=1e-6)),float(np.max(np.abs(actual-reference)))
warmup=[]
for i in range(50):
 latency,ok,diff=request()
 row={'event':'accuracy_check','index':i,'latency_s':latency,'correct':ok,'max_abs_error':diff}
 warmup.append(row);print(json.dumps(row),flush=True)
 if not ok:raise RuntimeError('Pilot accuracy failure: '+str(diff))
print(json.dumps({'event':'ready','torch':torch.__version__,'cuda':torch.version.cuda,'max_abs_error':max(r['max_abs_error'] for r in warmup),'checks':len(warmup),'max_latency_s':max(r['latency_s'] for r in warmup),'rtol':1e-4,'atol':1e-6}),flush=True)
def alarm(signum,frame):raise TimeoutError('request exceeded 40 s')
signal.signal(signal.SIGALRM,alarm)
for line in sys.stdin:
 parts=line.split()
 if not parts:continue
 if parts[0]=='quit':break
 if parts[0]=='load':
  mode=parts[1];duration=float(parts[2]);assert mode in ('memory','compute')
  size=int(parts[3]);batch=int(parts[4]);assert batch in (1,8)
  assert (mode=='memory' and size in (128,256,512)) or (mode=='compute' and size in (1024,2048,4096))
  if mode=='memory':
   buf=torch.ones(size*1024*1024//4,device='cuda',dtype=torch.float32)
   def work():buf.mul_(1.000001)
   allocated_bytes=buf.numel()*buf.element_size()
  else:
   left=torch.randn(size,size,device='cuda');right=torch.randn(size,size,device='cuda');out=torch.empty_like(left)
   def work():torch.mm(left,right,out=out)
   allocated_bytes=3*left.numel()*left.element_size()
  for _ in range(10):work()
  torch.cuda.synchronize()
  print(json.dumps({'event':'load_started','mode':mode,'size':size,'batch':batch,'buffer_bytes':allocated_bytes,'warmup_kernels':10}),flush=True)
  start=time.monotonic();last=start;count=0
  while time.monotonic()-start<duration:

   for _ in range(batch):work()
   torch.cuda.synchronize();count+=batch
   if time.monotonic()-last>=1:
    print(json.dumps({'event':'load_progress','mode':mode,'completed_kernels':count,'elapsed_s':time.monotonic()-start}),flush=True);last=time.monotonic()
  print(json.dumps({'event':'done','op':'load','mode':mode,'completed_kernels':count,'elapsed_s':time.monotonic()-start,'logical_work_per_kernel':allocated_bytes*2 if mode=='memory' else 2*size**3,'work_unit':'logical_bytes' if mode=='memory' else 'FLOP_estimate'}),flush=True)
  del work
  if mode=='memory':del buf
  else:del left,right,out
  torch.cuda.empty_cache()
  continue
 if parts[0]!='observe':raise ValueError(line)
 duration=float(parts[1]);start=time.monotonic();rows=[];i=0
 while time.monotonic()-start<duration:
  t=time.monotonic();signal.alarm(40)
  try:
   latency,ok,diff=request();r={'event':'request','id':i,'start':t,'latency_s':latency,'code':0 if ok else -1,'max_abs_error':diff}
  except Exception as e:r={'event':'request','id':i,'start':t,'latency_s':time.monotonic()-t,'code':999,'error':str(e)}
  finally:signal.alarm(0)
  print(json.dumps(r),flush=True);i+=1
  if r['code']!=0:break
 elapsed=time.monotonic()-start

 print(json.dumps({'event':'done','op':'observe','elapsed_s':elapsed,'attempts':i}),flush=True)
