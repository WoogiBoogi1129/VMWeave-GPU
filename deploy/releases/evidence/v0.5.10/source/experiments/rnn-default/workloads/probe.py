import argparse,base64,copy,gzip,json,os,time
from pathlib import Path
import torch
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['cpu','gpu'],default='gpu');p.add_argument('--case',default='lstm');a=p.parse_args()
root=Path('/results');torch.set_num_threads(1);torch.manual_seed(20261108)
torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
assert torch.backends.cudnn.enabled
assert os.environ.get('DISABLE_ADDMM_CUDA_LT') not in ['1']
def emit(stage,**kw):print(json.dumps(dict(stage=stage,**kw)),flush=True)
def sync():
 if a.mode=='gpu':torch.cuda.synchronize()
def snap(t):return t.detach().cpu().clone()
class Net(torch.nn.Module):
 def __init__(self):
  super().__init__();self.rnn=torch.nn.LSTM(28,32,batch_first=True);self.head=torch.nn.Linear(32,10)
 def forward(self,x):
  seq,(h,c)=self.rnn(x);return self.head(seq[:,-1,:]),seq,h,c
blob=gzip.decompress(base64.b64decode(Path('/work/mnist.b64').read_text()))
x=torch.frombuffer(bytearray(blob[:1024*784]),dtype=torch.uint8).reshape(1024,28,28).float()/255
y=torch.frombuffer(bytearray(blob[1024*784:1024*785]),dtype=torch.uint8).long()
emit('environment',torch=torch.__version__,cudnn=torch.backends.cudnn.version(),mode=a.mode,case=a.case)
if a.case=='basic':
 t=torch.arange(16,dtype=torch.float32).reshape(4,4);u=t.cuda();torch.testing.assert_close((u@u).cpu(),t@t);emit('PASS');raise SystemExit
if a.case in ['continuous','resume']:
 test_offset=1024*785
 tx=torch.frombuffer(bytearray(blob[test_offset:test_offset+256*784]),dtype=torch.uint8).reshape(256,28,28).float()/255
 ty=torch.frombuffer(bytearray(blob[test_offset+256*784:]),dtype=torch.uint8).long()
 initial=Net()
 def run_sequence(device,resume=False):
  model=copy.deepcopy(initial)
  checkpoint=torch.load('/work/checkpoint.pt',weights_only=True) if resume else None
  if checkpoint:model.load_state_dict(checkpoint['model'])
  model.to(device);opt=torch.optim.SGD(model.parameters(),lr=.01,foreach=False,fused=False)
  if checkpoint:opt.load_state_dict(checkpoint['optimizer'])
  start=checkpoint['step'] if checkpoint else 0
  losses=[]
  for step in range(start,128):
   off=(step%64)*16;inp=x[off:off+16].to(device);target=y[off:off+16].to(device)
   opt.zero_grad(set_to_none=True);logits=model(inp)[0];loss=torch.nn.functional.cross_entropy(logits,target);loss.backward();opt.step()
   value=loss.detach().cpu().item();assert __import__('math').isfinite(value);losses.append(value)
   if step==31 and device=='cuda':torch.save(dict(model={n:snap(t) for n,t in model.state_dict().items()},optimizer=opt.state_dict(),step=32),root/'checkpoint.pt')
   if (step+1)%16==0:emit('training_progress',device=device,step=step+1,loss=value)
  model.eval();outputs=[]
  with torch.no_grad():
   for off in range(0,256,16):outputs.append(snap(model(tx[off:off+16].to(device))[0]))
  logits=torch.cat(outputs);accuracy=(logits.argmax(1)==ty).float().mean().item();val_loss=torch.nn.functional.cross_entropy(logits,ty).item()
  result={'weight/'+n:snap(t) for n,t in model.state_dict().items()};result['validation_logits']=logits
  torch.save(result,root/(device+'-continuous.pt'))
  (root/(device+'-metrics.json')).write_text(json.dumps(dict(losses=losses,validation_loss=val_loss,accuracy=accuracy,steps=128-start),indent=2))
  emit('sequence_complete',device=device,accuracy=accuracy,validation_loss=val_loss);return result
 if a.case=='resume':
  assert a.mode=='gpu';reference=torch.load('/work/expected.pt',weights_only=True);actual=run_sequence('cuda',True)
 else:
  reference=run_sequence('cpu');actual=run_sequence('cuda') if a.mode=='gpu' else reference
 comparisons=[]
 for key in reference:
  r,g=reference[key],actual[key];comparisons.append(dict(tensor=key,max_abs=(r-g).abs().max().item(),pass_=torch.allclose(r,g,rtol=1e-4,atol=1e-6)))
 (root/'comparison.json').write_text(json.dumps(comparisons,indent=2));assert all(e['pass_'] for e in comparisons),[e for e in comparisons if not e['pass_']]
 emit('PASS');raise SystemExit
base=Net() if a.case!='mlp' else torch.nn.Sequential(torch.nn.Linear(28,32),torch.nn.ReLU(),torch.nn.Linear(32,10))
def train(device):
 model=copy.deepcopy(base);emit('model_to_start',device=device);model=model.to(device);sync();emit('model_to_done',device=device)
 opt=torch.optim.SGD(model.parameters(),lr=.01,foreach=False,fused=False);records={}
 for step in range(1,6):
  inp=x[:16].clone().to(device).requires_grad_();target=y[:16].to(device);sync();emit('input_ready',device=device,step=step)
  opt.zero_grad(set_to_none=True)
  if a.case=='mlp':
   logits=model(inp[:,-1,:]);extra={}
  else:
   emit('rnn_forward_start',device=device,step=step);seq,(h,c)=model.rnn(inp);sync();emit('rnn_forward_done',device=device,step=step)
   logits=model.head(seq[:,-1,:]);extra={'seq':seq,'h':h,'c':c}
  sync();emit('head_done',device=device,step=step)
  loss=torch.nn.functional.cross_entropy(logits,target);sync();emit('loss_done',device=device,step=step)
  loss.backward();sync();emit('backward_done',device=device,step=step)
  record={k:snap(v) for k,v in dict(extra,logits=logits,loss=loss,input_grad=inp.grad).items()}
  record.update({'grad/'+n:snap(v.grad) for n,v in model.named_parameters()})
  before={n:snap(v) for n,v in model.named_parameters()};opt.step();sync();emit('optimizer_done',device=device,step=step)
  assert any(not torch.equal(before[n],snap(v)) for n,v in model.named_parameters())
  record.update({'weight/'+n:snap(v) for n,v in model.named_parameters()})
  assert all(torch.isfinite(v).all().item() for v in record.values())
  if step in [1,5]:records[step]=record
 torch.save(records,root/(device+'.pt'));return records
cpu=train('cpu')
if a.mode=='gpu':
 gpu=train('cuda');errors=[]
 for step in cpu:
  for key in cpu[step]:
   ref,got=cpu[step][key],gpu[step][key];err=(ref-got).abs().max().item();ok=torch.allclose(ref,got,rtol=1e-4,atol=1e-6);errors.append(dict(step=step,tensor=key,max_abs=err,pass_=ok))
 (root/'comparison.json').write_text(json.dumps(errors,indent=2))
 assert all(e['pass_'] for e in errors),[e for e in errors if not e['pass_']]
emit('PASS')
