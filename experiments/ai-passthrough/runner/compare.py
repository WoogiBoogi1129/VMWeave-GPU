"""Compare every saved checkpoint tensor, including finite/shape checks."""
import hashlib,json
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parents[1]/'results/20261016';rows=[]
torch.set_num_threads(4)
for directory in sorted((ROOT/'pilot-vmweave').iterdir()):
 cand=directory/'tensors.pt'
 if not cand.exists():
  rows.append({'condition':directory.name,'status':'EXECUTION_FAILED' if (directory/'exit.json').exists() else 'UNMEASURED'});continue
 ref=ROOT/'pilot-passthrough'/cand.parent.name/'tensors.pt'
 if not ref.exists():rows.append({'condition':cand.parent.name,'status':'UNMEASURED'});continue
 cm=json.loads(cand.with_name('result.json').read_text());rm=json.loads(ref.with_name('result.json').read_text())
 for key in ['model','widths','batch','input','mode','torch','cuda','fixture_sha256','source_sha256']:assert cm[key]==rm[key],key
 cr=torch.load(cand,map_location='cpu',weights_only=True);rr=torch.load(ref,map_location='cpu',weights_only=True)
 assert cr.keys()==rr.keys()=={'1','10','100'}
 tensors=[]
 def compare(name,r,v):
  assert r.shape==v.shape and r.dtype==v.dtype
  r,v=r.double(),v.double();d=(r-v).abs();bad=(~torch.isfinite(r))|(~torch.isfinite(v))|(d>1e-6+1e-4*r.abs())
  tensors.append({'name':name,'elements':r.numel(),'exceeded':int(bad.sum()),'max_abs_error':float(d.max())})
 for step in rr:
  compare(step+'/loss',rr[step]['loss'],cr[step]['loss'])
  for category in ['weights','gradients']:
   assert rr[step][category].keys()==cr[step][category].keys()
   for name in rr[step][category]:compare(step+'/'+category+'/'+name,rr[step][category][name],cr[step][category][name])
 rows.append({'condition':cand.parent.name,'status':'PASS' if all(t['exceeded']==0 for t in tensors) else 'FAIL','reference_sha256':hashlib.file_digest(ref.open('rb'),'sha256').hexdigest(),'candidate_sha256':hashlib.file_digest(cand.open('rb'),'sha256').hexdigest(),'tensors':tensors})
(ROOT/'correctness.json').write_text(json.dumps({'rtol':1e-4,'atol':1e-6,'conditions':rows},indent=2)+'\n');print([(r['condition'],r['status']) for r in rows])
