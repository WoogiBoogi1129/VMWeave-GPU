"""CPU comparison of complete saved tensors; run with the common PyTorch bundle."""
import argparse,json,torch
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('reference');p.add_argument('candidate');p.add_argument('--out',required=True);a=p.parse_args()
torch.set_num_threads(1)
x=torch.load(a.reference,map_location='cpu',weights_only=True);y=torch.load(a.candidate,map_location='cpu',weights_only=True)
rows=[]
def compare(x,y,path=''):
 if isinstance(x,dict):
  assert x.keys()==y.keys()
  for k in x:compare(x[k],y[k],path+'/'+k)
 else:
  assert x.shape==y.shape
  delta=(x.double()-y.double()).abs()
  rows.append({'tensor':path,'shape':list(x.shape),'max_absolute_error':float(delta.max()),'finite':bool(torch.isfinite(x).all() and torch.isfinite(y).all()),'close':bool(torch.allclose(x,y,rtol=1e-4,atol=1e-6))})
compare(x,y)
result={'reference':Path(a.reference).name,'candidate':Path(a.candidate).name,'rtol':1e-4,'atol':1e-6,'passed':all(x['finite'] and x['close'] for x in rows),'tensors':rows}
Path(a.out).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'passed':result['passed'],'tensor_count':len(rows),'max_absolute_error':max(x['max_absolute_error'] for x in rows)}));assert result['passed']
