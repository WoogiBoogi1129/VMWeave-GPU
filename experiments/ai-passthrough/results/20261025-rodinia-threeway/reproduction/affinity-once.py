import json,os,time,sys,re
from pathlib import Path
config=Path(sys.argv[1]);out=Path(sys.argv[2]);end=time.monotonic()+360
while not config.exists():
 if time.monotonic()>end:raise TimeoutError('No target Pod UIDs')
 time.sleep(1)
rows=[]
for target in json.loads(config.read_text()):
 uid=target['uid'];assert re.fullmatch('[a-f0-9-]{36}',uid);cpus=set(target['cpus']);assert cpus in [set(range(32,40)),set(range(40,44))];found=[]
 for proc in Path('/proc').glob('[0-9]*'):
  try:
   group=(proc/'cgroup').read_text()
   if uid not in group and uid.replace('-','_') not in group:continue
   cmd=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
   if not any(pat in cmd for pat in target['patterns']):continue
   threads=[]
   for task in (proc/'task').iterdir():
    tid=int(task.name);os.sched_setaffinity(tid,cpus);actual=sorted(os.sched_getaffinity(tid));assert actual==sorted(cpus);threads.append(tid)
   found.append({'pid':int(proc.name),'command':cmd,'threads':threads})
  except (FileNotFoundError,ProcessLookupError):continue
 assert found,target
 rows.append({'uid':uid,'cpus':sorted(cpus),'processes':found})
out.write_text(json.dumps(rows,indent=2));out.chmod(0o644)
