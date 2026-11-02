"""Fresh application processes, immutable per-attempt output, bounded timeouts."""
from backends import *
import threading
CASES=[(m,b,i) for m in ['small','large'] for b in [32,1024] for i in ['resident','h2d']]+[(m,1024,'roundtrip') for m in ['small','large']]
def slug(case):return '-'.join(map(str,case))
def cpu_monitor(s,path,stop):
 pods=json.loads(k('get','pods','-n',s['namespace'],'-o','json'))['items']
 stopfile=B/('monitor-stop-'+str(time.time_ns()))
 targets={p['metadata']['uid']:p['metadata']['name'] for p in pods if p['metadata']['name'].startswith('virt-launcher-'+s['name']+'-') or p['metadata']['name']==s.get('worker')}
 code='''import pathlib,json,time
root=pathlib.Path('/sys/fs/cgroup/kubepods.slice')
paths={}
for uid,name in TARGETS.items():
 matches=list(root.glob('**/*pod'+uid.replace('-','_')+'.slice/cpu.stat'))
 assert len(matches)==1,(uid,len(matches))
 paths[name]=matches[0]
while not pathlib.Path(STOPFILE).exists():
 row={'utc':time.time(),'pods':{}}
 for name,p in paths.items():
  try:
   row['pods'][name]={'cpu':dict((k,int(v)) for k,v in (l.split() for l in p.read_text().splitlines())), 'memory_bytes':int(p.with_name('memory.current').read_text())}
  except OSError:pass
 print(json.dumps(row),flush=True);time.sleep(0.5)
'''.replace('TARGETS',repr(targets)).replace('STOPFILE',repr(str(stopfile)))
 with path.open('w') as f:
  proc=S.Popen(['kubectl','exec','-i','-n',NS,'admin','--','chroot','/host','timeout','800','python3','-u','-'],stdin=S.PIPE,stdout=f,stderr=S.DEVNULL,text=True)
  proc.stdin.write(code);proc.stdin.close()
  stop.wait();stopfile.touch()
  try:proc.wait(timeout=3)
  except S.TimeoutExpired:proc.terminate()
  try:proc.wait(timeout=5)
  except S.TimeoutExpired:proc.kill();proc.wait()

def gpu_monitor(s,path,stop):
 fields='uuid,utilization.gpu,memory.used,clocks.sm,power.draw,temperature.gpu'
 cmd=['nvidia-smi','-i',GPU,'--query-gpu='+fields,'--format=csv,noheader,nounits']
 if s['mode']=='passthrough':cmd=s['ssh']+['sudo env LD_LIBRARY_PATH=/opt/flyt-evidence/driver /opt/flyt-evidence/driver/nvidia-smi --query-gpu='+fields+' --format=csv,noheader,nounits']
 with path.open('w') as f:
  while not stop.is_set():
   t=time.time()
   try:
    p=S.run(cmd,capture_output=True,text=True,timeout=8);row={'utc':t,'end_utc':time.time(),'returncode':p.returncode,'csv':p.stdout.strip()}
   except S.TimeoutExpired:row={'utc':t,'error':'monitor timeout'}
   f.write(json.dumps(row)+'\n');f.flush();stop.wait(2)

def measure(s,case,phase,label,steps=32,warmup=32,correctness=False,device='cuda'):
 dest=O/phase/label/s['mode']/slug(case)
 if device=='cpu':dest=dest/'cpu'
 dest.mkdir(parents=True,exist_ok=False)
 prefix='/tmp/training/'+phase+'-'+label+'-'+slug(case)+'-'+device
 args=['--model',case[0],'--batch',case[1],'--input',case[2],'--steps',steps,'--warmup',warmup,'--out',prefix,'--device',device]
 if correctness:args+=['--correctness']
 clock=[]
 for _ in range(3):
  t=time.time();v=float(remote(s,'date +%s.%N'));end=time.time();clock.append({'host_before':t,'guest':v,'host_after':end,'offset':v-(t+end)/2,'uncertainty':(end-t)/2})
 save(dest/'clock.json',clock)
 stop=threading.Event();threads=[]
 if not correctness:
  threads=[threading.Thread(target=cpu_monitor,args=(s,dest/'cpu.jsonl',stop),daemon=True),threading.Thread(target=gpu_monitor,args=(s,dest/'gpu.jsonl',stop),daemon=True)]
  for t in threads:t.start()
 try:
  with (dest/'stdout.txt').open('w') as out,(dest/'stderr.txt').open('w') as err:
   start=time.time();p=S.run(command(s,args,600),stdout=out,stderr=err,timeout=630)
   save(dest/'exit.json',{'returncode':p.returncode,'start_utc':start,'end_utc':time.time()})
   if p.returncode:raise RuntimeError('Benchmark failed: '+str(dest))
  S.run(s['scp']+['ubuntu@'+s['ip']+':'+prefix+'.json',str(dest/'result.json')],check=True,capture_output=True)
  result=json.loads((dest/'result.json').read_text());assert result['completed']
  if correctness:
   blob=B/'tensors'/s['mode']/(slug(case)+'-'+device+'.pt');blob.parent.mkdir(parents=True,exist_ok=True)
   S.run(s['scp']+['ubuntu@'+s['ip']+':'+prefix+'.pt',str(blob)],check=True,capture_output=True)
   save(dest/'tensors.json',{'sha256':hashlib.sha256(blob.read_bytes()).hexdigest(),'bytes':blob.stat().st_size,'local_blob':str(blob.relative_to(R))})
  print(phase,label,s['mode'],slug(case),'PASS',result.get('samples_per_second'),flush=True)
  return result
 finally:
  stop.set()
  for t in threads:t.join(timeout=12)

if __name__=='__main__':
 import sys
 mode=sys.argv[1];s=None
 try:
  s=open_mode(mode,'qualification')
  for case in CASES:measure(s,case,'qualification','initial',correctness=True)
  if mode=='passthrough':
   for case in CASES:
    if case[0]=='small':measure(s,case,'qualification','initial',correctness=True,device='cpu')
 finally:
  if s:close_mode(s)
