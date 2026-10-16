"""Stage barriers for real PyTorch allocator, loss and cleanup observations."""
import os,json,time,gc
os.environ['DISABLE_ADDMM_CUDA_LT']='1';os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
import torch
torch.set_num_threads(1);torch.manual_seed(20261016);torch.backends.cuda.matmul.allow_tf32=False
assert torch.cuda.is_available() and torch.cuda.device_count()==1

def stage(name,**kw):
 torch.cuda.synchronize();f,t=torch.cuda.mem_get_info()
 row={'stage':name,'guest_utc':time.time(),'free':f,'total':t,'allocated':torch.cuda.memory_allocated(),'reserved':torch.cuda.memory_reserved(),'peak_allocated':torch.cuda.max_memory_allocated(),'peak_reserved':torch.cuda.max_memory_reserved(),**kw}
 print(json.dumps(row),flush=True)
 if input()!='next':raise RuntimeError('host barrier missing')
stage('torch-context',torch=torch.__version__,cuda=torch.version.cuda)
net=torch.nn.Sequential(torch.nn.Linear(1024,2048),torch.nn.ReLU(),torch.nn.Linear(2048,1024)).cuda()
x=torch.randn(32,1024).cuda();y=torch.randn(32,1024).cuda();opt=torch.optim.SGD(net.parameters(),lr=.01,foreach=False,fused=False)
stage('model-data')
losses=[]
for i in range(20):
 opt.zero_grad(set_to_none=True);loss=torch.nn.functional.mse_loss(net(x),y);loss.backward();opt.step();torch.cuda.synchronize();losses.append(loss.detach().cpu().item())
 if i==0:stage('first-training-step',loss=losses[-1])
assert losses[-1]<losses[0]
stage('training-complete',initial_loss=losses[0],final_loss=losses[-1],steps=20)
del loss,opt,x,y,net;gc.collect();stage('tensors-deleted')
torch.cuda.empty_cache();stage('empty-cache')
print(json.dumps({'stage':'done','status':'PASS'}),flush=True)
