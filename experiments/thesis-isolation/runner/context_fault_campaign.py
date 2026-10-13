"""E3 bounded context fault: 60s baseline and >=60s observation after fault."""
import fcntl,hashlib
from campaign import *
lock=(BASE/'context-fault.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
out=OUT/'context-fault-20261013';out.mkdir(exist_ok=False)
save(out/'protocol.json',{'experiment':'E3','gpu':GPU,'fault':'one null-address store in test CUDA context; zero kernel arguments','baseline_s':60,'concurrent_window_s':100,'post_fault_minimum_s':60,'request_timeout_s':40,'trials':10,'source_commit':call(['git','rev-parse','HEAD']).strip(),'probe_sha256':hashlib.sha256((BASE/'artifacts/context-fault').read_bytes()).hexdigest()})
results=[]
for rep in range(1,6):
 for direction in ['ab','ba']:
  name=f'iso-e3-r{rep}-{direction}-1013';trial=out/name;trial.mkdir();sessions=[];probes=[]
  r={'name':name,'repetition':rep,'direction':direction,'status':'INCONCLUSIVE'}
  save(out/'status.json',{'state':'PREPARING','trial':name,'completed':len(results),'total':10,'utc':time.time()});print('START',name,flush=True)
  try:
   inv=call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
   if GPU in inv:raise RuntimeError('Test GPU has an existing compute process')
   for i,slot in enumerate(['a','b']):
    s=Session(name+'-'+slot,slot=slot,memory=2048,cap=50);sessions.append(s);s.prepare()
    call(s.scp+[BASE/'artifacts/context-fault','ubuntu@'+s.ip+':/tmp/perf/context-fault'])
    p=Probe(s,202610130+rep*1000+i*100,program='context-fault');probes.append(p);freeze(s)
   a,b=probes if direction=='ab' else list(reversed(probes));before_worker=a.s.get('pod',a.s.worker)
   save(out/'status.json',{'state':'BASELINE','trial':name,'completed':len(results),'total':10,'utc':time.time()})
   before=a.command('observe 60',100);save(trial/'baseline.json',before)
   assert all(x['code']==0 for x in before if x['event']=='request'),'Baseline error'
   save(out/'status.json',{'state':'FAULT_AND_OBSERVATION','trial':name,'completed':len(results),'total':10,'utc':time.time()})
   with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
    future=pool.submit(a.command,'observe 100',140)
    fault=b.command('fault',40);save(trial/'fault.json',fault)
    confirmed=time.time();observed=future.result();save(trial/'observer.json',observed)
   assert time.time()-confirmed>=60,'Insufficient post-fault observation'
   f=next(x for x in fault if x['event']=='fault');r['fault']=f
   req=[x for x in observed if x['event']=='request'];assert req
   after_worker=a.s.get('pod',a.s.worker);save(trial/'observer-worker-after.json',after_worker)
   alive=after_worker['metadata']['uid']==before_worker['metadata']['uid'] and after_worker['status']['phase']=='Running' and all(x.get('ready') and x.get('restartCount',0)==0 for x in after_worker['status'].get('containerStatuses',[]))
   r.update(observer_requests=len(req),observer_errors=sum(x['code']>0 for x in req),observer_mismatches=sum(x['code']==-1 for x in req),observer_worker_alive=alive,post_fault_observation_s=time.time()-confirmed)
   if f['load']!=0 or f['abi']!=0 or f['launch']!=0 or f['sync'] not in [700,710,719]:r['reason']='Actual expected CUDA execution fault not established'
   else:r['status']='PASS' if all(x['code']==0 for x in req) and alive else 'FAIL'
  except Exception as e:r['error']=str(e)
  finally:
   save(trial/'verdict.json',r)
   for p in probes:
    try:p.close()
    except Exception as e:r.setdefault('cleanup_errors',[]).append(str(e))
   for s in sessions:
    try:s.close()
    except Exception as e:r.setdefault('cleanup_errors',[]).append(str(e))
   save(trial/'verdict.json',r)
  results.append(r);save(out/'results.json',results);print('END',name,r['status'],flush=True)
  if r['status']!='PASS' or r.get('cleanup_errors'):
   save(out/'status.json',{'state':'STOPPED','completed':len(results),'total':10,'result':r,'utc':time.time()});raise SystemExit(1)
save(out/'status.json',{'state':'COMPLETE','completed':10,'total':10,'utc':time.time()})
