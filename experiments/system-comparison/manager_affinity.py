"""Pin every thread in exactly one dedicated legacy manager Pod."""
import json,os,re,sys
from pathlib import Path
uid,cpulist=sys.argv[1:];assert re.fullmatch('[a-f0-9-]{36}',uid)
first,last=map(int,cpulist.split('-'));assert 0<=first<=last<128
cpus=set(range(first,last+1));rows=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  cg=(p/'cgroup').read_text()
  if uid not in cg and uid.replace('-','_') not in cg:continue
  threads=[]
  for t in (p/'task').iterdir():
   tid=int(t.name);os.sched_setaffinity(tid,cpus);actual=sorted(os.sched_getaffinity(tid));assert actual==sorted(cpus)
   threads.append({'tid':tid,'cpus':actual})
  rows.append({'pid':int(p.name),'command':(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace'),'threads':threads})
 except (FileNotFoundError,ProcessLookupError):continue
assert rows,'No process matched exact Pod UID'
print(json.dumps({'pod_uid':uid,'cpu_set':cpulist,'processes':rows}))
