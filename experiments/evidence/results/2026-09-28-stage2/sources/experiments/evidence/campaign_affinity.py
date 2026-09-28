"""Executed in the campaign host-PID helper, restricted to one verified Pod UID."""
import json,os,re,sys
from pathlib import Path
uid,cpulist=sys.argv[1:]
if not re.fullmatch('[a-f0-9-]{36}',uid):raise ValueError('Pod UID required')
start,end=map(int,cpulist.split('-'));assert 0<=start<=end<128
cpus=set(range(start,end+1));rows=[]
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:
  cgroup=(proc/'cgroup').read_text()
  if uid not in cgroup and uid.replace('-','_') not in cgroup:continue
  command=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  if not any(x in command for x in ('qemu-kvm','flyt-shm-worker')):continue
  threads=[]
  for task in (proc/'task').iterdir():
   tid=int(task.name);os.sched_setaffinity(tid,cpus);actual=sorted(os.sched_getaffinity(tid))
   assert actual==sorted(cpus);threads.append({'tid':tid,'cpus':actual})
  rows.append({'pid':int(proc.name),'command':command,'threads':threads,'numa_maps':(proc/'numa_maps').read_text()})
 except (FileNotFoundError,ProcessLookupError):continue
if not rows:raise RuntimeError('No QEMU/Worker process matched exact Pod UID')
print(json.dumps({'pod_uid':uid,'cpu_set':cpulist,'processes':rows}))
