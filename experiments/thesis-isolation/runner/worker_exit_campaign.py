"""E4 targeted Worker exit: 60s baseline and >=60s observation after fault."""
import fcntl,hashlib
from campaign import *
lock=(BASE/'worker-exit.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
out=OUT/'worker-exit-20261013';out.mkdir(exist_ok=False)
save(out/'protocol.json',{'experiment':'E4','gpu':GPU,'fault':'SIGKILL of exact Pod-owned slot-0 CUDA Worker via pidfd','baseline_s':60,'concurrent_window_s':100,'post_fault_minimum_s':60,'request_timeout_s':40,'trials':10,'source_commit':call(['git','rev-parse','HEAD']).strip(),'probe_sha256':hashlib.sha256((BASE/'artifacts/context-fault').read_bytes()).hexdigest()})
results=[]
for rep in range(1,6):
 for direction in ['ab','ba']:
  name=f'iso-e4-r{rep}-{direction}-1013';trial=out/name;trial.mkdir();sessions=[];probes=[]
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
    channel=b.s.get(CHAN,b.s.name);pod=b.s.get('pod',b.s.worker)
    assert channel['metadata']['uid']==b.s.uid and channel['status']['workerPodUID']==pod['metadata']['uid']
    assert channel['status']['gpuUUID']==GPU and channel['status']['phase']=='Ready'
    assert any(x.get('uid')==b.s.uid for x in pod['metadata'].get('ownerReferences',[]))
    save(trial/'target-channel.json',channel);save(trial/'target-pod.json',pod)
    code=(ROOT/'experiments/thesis-isolation/runner/terminate_test_worker.py').read_text()
    killed=json.loads(k('exec','-i','-n',NS,HELPER,'--','chroot','/host','python3','-',pod['metadata']['uid'],input=code,timeout=30));save(trial/'termination.json',killed)
    confirmed=time.time()
    try:
     target_rows=b.command('observe 1',40)
     target_req=[x for x in target_rows if x['event']=='request']
     target_failed=bool(target_req) and all(x['code']!=0 for x in target_req)
     target_result={'rows':target_rows,'failed_as_expected':target_failed}
    except TimeoutError as e:target_failed=True;target_result={'timeout_s':40,'error':str(e),'failed_as_expected':True}
    except RuntimeError as e:target_failed=True;target_result={'session_exit':str(e),'failed_as_expected':True}
    save(trial/'target-request.json',target_result)
    observed=future.result();save(trial/'observer.json',observed)
   # Extend observation if process identity lookup/termination consumed the initial window.
   if time.time()-confirmed<60:
    extra=a.command('observe 60',100);save(trial/'observer-extension.json',extra)
   else:extra=[]
   r.update(termination=killed,target_request=target_result)
   req=[x for x in observed+extra if x['event']=='request'];assert req
   after_worker=a.s.get('pod',a.s.worker);save(trial/'observer-worker-after.json',after_worker)
   alive=after_worker['metadata']['uid']==before_worker['metadata']['uid'] and after_worker['status']['phase']=='Running' and all(x.get('ready') and x.get('restartCount',0)==0 for x in after_worker['status'].get('containerStatuses',[]))
   r.update(observer_requests=len(req),observer_errors=sum(x['code']>0 for x in req),observer_mismatches=sum(x['code']==-1 for x in req),observer_worker_alive=alive,post_fault_observation_s=time.time()-confirmed)
   r['status']='PASS' if all(x['code']==0 for x in req) and alive and target_failed and killed['exit_confirmed'] else 'FAIL'
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
