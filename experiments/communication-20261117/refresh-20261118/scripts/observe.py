"""Run in the owned admin Pod: cumulative, disjoint Pod cgroups and GPU1 state."""
import pathlib,json,time,subprocess,sys
out=pathlib.Path(sys.argv[1]);uids=json.loads(sys.argv[2]);gpu=sys.argv[3]
paths={}
for label,uid in uids.items():
 matches=list(pathlib.Path('/sys/fs/cgroup').rglob('*pod'+uid.replace('-','_')+'.slice'))
 if not matches:matches=list(pathlib.Path('/sys/fs/cgroup').rglob('pod'+uid))
 if len(matches)==1:paths[label]=matches[0]
iteration=0
with out.open('w') as f:
 while not out.with_suffix('.stop').exists():
  row={'utc_ns':time.time_ns(),'cpu':{},'cgroups':{k:str(v) for k,v in paths.items()}}
  for key,p in paths.items():
   try:row['cpu'][key]={a:int(b) for a,b in (line.split() for line in (p/'cpu.stat').read_text().splitlines())}
   except OSError:pass
  try:row['gpu']=subprocess.check_output(['nvidia-smi','-i',gpu,'--query-gpu=uuid,temperature.gpu,clocks.sm,clocks.mem,power.draw,utilization.gpu,memory.used,clocks_event_reasons.active','--format=csv,noheader,nounits'],text=True,timeout=3).strip()
  except Exception as e:row['gpu_error']=str(e)
  if iteration%5==0:
   try:
    apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'],text=True,timeout=3)
    row['target_processes']=[]
    for line in apps.splitlines():
     if not line.startswith(gpu):continue
     fields=[x.strip() for x in line.split(',')];pid=int(fields[1])
     try:cg=pathlib.Path('/proc',str(pid),'cgroup').read_text()
     except FileNotFoundError:continue
     owned=any(u in cg or u.replace('-','_') in cg for u in uids.values())
     row['target_processes'].append({'pid':pid,'name':fields[2],'owned':owned})
     if not owned:out.with_suffix('.interference').write_text(json.dumps(row))
   except Exception as e:row['process_check_error']=str(e)
  iteration+=1
  f.write(json.dumps(row)+'\n');f.flush();time.sleep(1)
