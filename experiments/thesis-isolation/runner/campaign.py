"""Actual two-VM experiment runner; raw JSONL is retained including failures."""
import argparse,queue,concurrent.futures
from session import *
TIMEOUT=40
class Probe:
 def __init__(self,s,seed):
  self.s=s;self.q=queue.Queue();self.rows=[]
  self.log=(s.out/'requests-events.jsonl').open('w');self.err=(s.out/'probe-stderr.txt').open('w')
  self.p=subprocess.Popen(s.command('isolation',[seed]),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.err,text=True,bufsize=1)
  def reader():
   for line in self.p.stdout:
    try:r=json.loads(line)
    except ValueError:r={'event':'unparsed','text':line}
    r['received_host_utc']=time.time();self.rows.append(r);self.log.write(json.dumps(r)+'\n');self.log.flush();self.q.put(r)
   self.q.put({'event':'eof'})
  self.thread=threading.Thread(target=reader,daemon=True);self.thread.start();self.ready=self.until('ready',TIMEOUT)
 def until(self,event,timeout):
  end=time.monotonic()+timeout;rows=[]
  while time.monotonic()<end:
   try:r=self.q.get(timeout=max(.01,end-time.monotonic()))
   except queue.Empty:break
   rows.append(r)
   if r['event']==event:return r if event=='ready' else rows
   if r['event'] in ['eof','init_error']:raise RuntimeError(str(r))
  row={'event':'harness_timeout','waiting_for':event,'timeout_s':timeout,'received_host_utc':time.time()};self.log.write(json.dumps(row)+'\n');self.log.flush();raise TimeoutError(str(row))
 def command(self,line,seconds=TIMEOUT):
  self.p.stdin.write(line+'\n');self.p.stdin.flush();return self.until('done',seconds)
 def close(self):
  try:self.p.stdin.write('quit\n');self.p.stdin.flush();self.p.wait(timeout=TIMEOUT)
  except (BrokenPipeError,subprocess.TimeoutExpired):self.p.kill();self.p.wait()
  self.thread.join(timeout=5);self.log.close();self.err.close()
def freeze(s):
 c=wait(lambda: (c if (c:=s.get(CHAN,s.name))['status']['phase']=='Ready' else None),30);p=s.get('pod',s.worker)
 save(s.out/'channel-running.json',c)
 save(s.out/'worker-identity.json',{'uid':p['metadata']['uid'],'images':p['status'].get('containerStatuses'),'annotations':p['metadata'].get('annotations'),'resources':[x.get('resources') for x in p['spec']['containers']]})
 if c['status']['phase']!='Ready':raise RuntimeError('Actual probe succeeded but channel not Ready')
 return c

def pair(experiment,rep,direction):
 name=f'iso-{experiment.lower()}-r{rep}-{direction}';out=OUT/'pairs'/name;out.mkdir(parents=True,exist_ok=False)
 # Role exchange does not change placement. Small quota follows B for ab, A for ba.
 sessions=[Session(name+'-'+slot,slot=slot,memory=(4096 if slot=='a' else 1024) if experiment=='E1' else 2048) for slot in ['a','b']]
 probes=[];result={'experiment':experiment,'repetition':rep,'direction':direction,'status':'INCONCLUSIVE','request_timeout_s':TIMEOUT}
 try:
  inv=call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
  if GPU in inv:raise RuntimeError('Test GPU has existing compute process')
  for i,s in enumerate(sessions):
   s.prepare();probes.append(Probe(s,2026101200+rep*100+i*10000));freeze(s)
  ca,cb=[s.get(CHAN,s.name) for s in sessions]
  if ca['metadata']['uid']==cb['metadata']['uid']:raise RuntimeError('Same channel')
  result['sessions']=[s.name for s in sessions];result['ready']=[p.ready for p in probes]
  a,b=probes if direction=='ab' else list(reversed(probes))
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
   if experiment=='E1':
    f=pool.submit(a.command,'observe 60',100);time.sleep(2)
    (out/'gpu-before-oom.txt').write_text(call(['nvidia-smi','--query-gpu=uuid,memory.free,memory.used','--format=csv']))
    attack=b.command('oom '+str(b.s.memory*1024**2),TIMEOUT)
    (out/'gpu-after-oom.txt').write_text(call(['nvidia-smi','--query-gpu=uuid,memory.free,memory.used','--format=csv']))
    observer=f.result();result['attack']=attack
    req=[r for r in observer if r['event']=='request'];recovery=next((r for r in attack if r['event']=='recovery'),{})
    result['status']='PASS' if recovery.get('oom_code')==2 and recovery.get('code')==0 and req and all(r['code']==0 for r in req) and max(r['sum'] for r in attack if r['event']=='allocation')<=b.s.memory*1024**2 else 'FAIL'
   else:raise ValueError('Experiment not implemented by this runner yet')
  result['observer_attempts']=len(req);result['observer_errors']=sum(r['code']>0 for r in req);result['observer_mismatches']=sum(r['code']==-1 for r in req)
 except Exception as e:
  result['error']=str(e);print('PAIR_ERROR',name,str(e),flush=True)
 finally:
  for p in probes:
   try:p.close()
   except Exception as e:result.setdefault('cleanup_errors',[]).append(str(e))
  for s in sessions:
   try:s.close()
   except Exception as e:result.setdefault('cleanup_errors',[]).append(str(e))
  save(out/'verdict.json',result)
 print('PAIR_COMPLETE',name,result['status'],flush=True)
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('experiment',choices=['E1']);p.add_argument('--repetitions',default='1,2,3,4,5');p.add_argument('--directions',default='ab,ba');a=p.parse_args()
 for rep in map(int,a.repetitions.split(',')):
  for direction in a.directions.split(','):
   prior=OUT/'pairs'/f'iso-{a.experiment.lower()}-r{rep}-{direction}'/'verdict.json'
   if prior.exists():
    old=json.loads(prior.read_text())
    if old.get('status') in ['PASS','FAIL'] and not old.get('cleanup_errors') and not old.get('error'):
     print('PRESERVED',prior,flush=True);continue
    raise SystemExit('Incomplete previous run requires inspection: '+str(prior))
   r=pair(a.experiment,rep,direction)
   if r.get('cleanup_errors') or r.get('error'):raise SystemExit('Stopped at infrastructure/probe failure; inspect raw evidence')
