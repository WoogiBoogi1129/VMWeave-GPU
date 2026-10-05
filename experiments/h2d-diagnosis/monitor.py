from common import *
os.sched_setaffinity(0,{48,49,50,51})
(OUT/'monitoring').mkdir(exist_ok=True)
while not (BASE/'stop-monitor').exists():
 try:
  states=json.loads((BASE/'live-state.json').read_text())
  for name,r in states.items():
   if time.time()-r['updated']>5:continue
   ident=json.loads((OUT/'runs'/name/'identity.json').read_text());observations=[]
   for role,key in [('worker','worker_uid'),('cell','cell_uid'),('manager','manager_uid'),('launcher','launcher_uid')]:
    if key not in ident:continue
    uid=ident[key]
    for cg in Path('/sys/fs/cgroup/kubepods.slice').glob('*/*pod*.slice'):
     if uid.replace('-','_') not in cg.name and uid not in cg.name:continue
     observations.append({'role':role,'uid':uid,'cpu':{k:int(v) for k,v in (l.split() for l in (cg/'cpu.stat').read_text().splitlines())},'memory_bytes':int((cg/'memory.current').read_text())})
   with (OUT/'monitoring/cpu.jsonl').open('a') as f:f.write(json.dumps({'utc':time.time(),'run_id':name,'pods':observations})+'\n')
 except (FileNotFoundError,ValueError):pass
 time.sleep(1)
