import json,subprocess as S,time,hashlib,shlex,os
from pathlib import Path
R=Path(__file__).resolve().parents[3]
O=Path(__file__).resolve().parents[1]
B=R/'.local/communication-20261117'
NS='comm-20261117'; VNS='vmweave-test-a'; NAME='comm-20261117'
GPU='GPU-772181af-05a4-0c24-de59-8487bd37c142'; NODE='gpu-4'
H='/var/lib/vmweave/communication-20261117'
IM=json.loads((R/'deploy/releases/v0.5.11.json').read_text())['images']
LABEL={'experiment.vmweave.io/campaign':NAME}
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+'\n')
def call(a,**kw):return S.check_output(list(map(str,a)),text=True,timeout=kw.pop('timeout',180),**kw)
def k(*a,**kw):return call(['kubectl','--request-timeout=30s',*a],**kw)
def get(kind,name,ns=NS):
 t=k('get',kind,name,'-n',ns,'--ignore-not-found','-o','json');return json.loads(t) if t.strip() else None
def create(x):
 x['metadata'].setdefault('labels',{}).update(LABEL)
 p=B/'owned.json';owned=json.loads(p.read_text()) if p.exists() else []
 y=json.loads(k('create','-f','-','-o','json',input=json.dumps(x)))
 owned.append({'kind':x['kind'],'name':y['metadata']['name'],'namespace':y['metadata'].get('namespace'),'uid':y['metadata']['uid']});save(p,owned)
 return y
def wait(f,seconds=300):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  x=f()
  if x:return x
  time.sleep(2)
 raise TimeoutError('wait expired')
def admin(code,timeout=180):return k('exec','-i','-n',NS,'admin','--','chroot','/host','python3','-',input=code,timeout=timeout)
def patch(kind,name,obj,ns=NS):return k('patch',kind,name,'-n',ns,'--type=merge','-p',json.dumps(obj))
def remove(kind,name,ns=NS):
 x=get(kind,name,ns)
 if not x:return
 owned=json.loads((B/'owned.json').read_text())
 assert any(r['uid']==x['metadata']['uid'] for r in owned),(kind,name,'not owned')
 return k('delete',kind,name,'-n',ns,'--wait=true','--timeout=120s')
