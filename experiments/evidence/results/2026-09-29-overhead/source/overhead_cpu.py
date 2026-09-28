"""Run inside the existing host-PID helper. Sample exclusive pod cgroups."""
import json,os,sys,time
from pathlib import Path
os.sched_setaffinity(0,{48,49,50,51})
state=Path(sys.argv[1])
while True:
 t=time.time();out={'utc':t,'pods':[],'errors':[]}
 try:
  s=json.loads(state.read_text());out['session']=s.get('session');out['path']=s.get('path');uids=s.get('uids',{})
  found={}
  for p in Path('/sys/fs/cgroup/kubepods.slice').glob('*/*pod*.slice'):
   for role,uid in uids.items():
    if uid in p.name or uid.replace('-','_') in p.name:found[role]=(uid,str(p))
  for role,(uid,cg) in found.items():
   f=Path(cg)/'cpu.stat'
   vals=dict(line.split() for line in f.read_text().splitlines());out['pods'].append({'role':role,'uid':uid,'cgroup':cg,**{k:int(v) for k,v in vals.items()}})
 except Exception as e:out['errors'].append(str(e))
 print(json.dumps(out),flush=True);time.sleep(max(.05,1-(time.time()-t)))
