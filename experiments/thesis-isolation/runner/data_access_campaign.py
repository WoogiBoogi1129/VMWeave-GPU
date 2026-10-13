"""E2: controller-selected synthetic buffers; independent pairs per access path."""
import fcntl,hashlib
from campaign import *
lock=(BASE/'data-access.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
out=OUT/'data-access-20261013';out.mkdir(exist_ok=False)
paths=['rawread','rawwrite','read','write']
plan=[{'rep':r,'direction':d,'path':p} for r in range(1,6) for d in ['ab','ba'] for p in paths]
save(out/'protocol.json',{'experiment':'E2 data access isolation','gpu':GPU,'paths':paths,'repetitions_per_path_per_direction':5,'planned_trials':40,'buffer_bytes':4096,'access_bytes':4,'write_pattern':'0xdeadbeef','kernel_pointer_validation':'enabled; both device pointers declared as pointers','rule':'Only controller-provided synthetic target. Stop entire campaign on target disclosure/modification, infrastructure failure, or cleanup failure. Guest rejection does not establish GPU kernel isolation.','probe_sha256':hashlib.sha256((BASE/'artifacts/data-access').read_bytes()).hexdigest(),'source_commit':call(['git','rev-parse','HEAD']).strip(),'pending_source_changes':call(['git','diff','--stat'])})
completed=[]
for job in plan:
 name=f"iso-access-r{job['rep']}-{job['direction']}-{job['path']}-1013"
 trial=out/name;trial.mkdir();sessions=[];probes=[];result={**job,'name':name,'status':'INCONCLUSIVE'}
 save(out/'status.json',{'state':'RUNNING','current':job,'trial':name,'completed':len(completed),'total':40,'utc':time.time()})
 print('START',name,flush=True)
 try:
  inventory=call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
  if GPU in inventory:raise RuntimeError('Unexpected compute process on test GPU')
  for i,slot in enumerate(['a','b']):
   s=Session(name+'-'+slot,slot=slot,memory=2048,cap=50);sessions.append(s);s.prepare()
   call(s.scp+[BASE/'artifacts/data-access','ubuntu@'+s.ip+':/tmp/perf/data-access'])
   seed=202610130+len(completed)*1000+i*100
   p=Probe(s,seed,program='data-access');probes.append(p);freeze(s)
  target,requester=probes if job['direction']=='ab' else list(reversed(probes))
  result['target']=target.ready;result['requester']=requester.ready
  result['session_uids']=[s.uid for s in sessions]
  assert target.ready['seed']!=requester.ready['seed']
  before=target.command('check');assert before[0]['code']==0
  target_id=target.ready['handle' if job['path'].startswith('raw') else 'address']
  save(trial/'approved-target.json',{'target':target.ready,'requester':requester.ready,'target_session':target.s.uid,'requester_session':requester.s.uid,'bytes':4,'buffer_length':4096,'operation':job['path']})
  events=requester.command(f"{job['path']} {target_id}")
  access=next(r for r in events if r['event']=='access');after=target.command('check');check=next(r for r in after if r['event']=='check')
  result.update(access=access,target_before=before,target_after=after)
  leaked=job['path'] in ['read','rawread'] and access.get('observed')==target.ready['seed'] and access.get('code',access.get('copy',0))==0
  changed=check['code']==-1
  if leaked or changed:result.update(status='FAIL',disclosure=leaked,target_modified=changed)
  elif check['code']!=0:result.update(status='INCONCLUSIVE',reason='Target check failed')
  elif job['path'].startswith('raw'):
   result.update(status='NO_CROSS_ACCESS_OBSERVED',handle_alias=target.ready['handle']==requester.ready['handle'],api_rejected=access['code']!=0,layer='Existing Worker request/handle resolution; equal handles may resolve requester-owned allocation')
  elif access['launch']!=0:
   result.update(status='NO_CROSS_ACCESS_OBSERVED',layer='Kernel launch rejected; Guest pointer lookup is an applicable rejection path from source review',gpu_kernel_path_verified=False)
  else:
   result.update(status='NO_CROSS_ACCESS_OBSERVED',layer='Registered pointer kernel launch',gpu_kernel_path_verified=access['sync']==0 and access['copy']==0)
  result['channels_after']=[s.get(CHAN,s.name).get('status',{}) for s in sessions]
 except Exception as e:result.update(status='INCONCLUSIVE',error=str(e))
 finally:
  save(trial/'verdict.json',result)
  for p in probes:
   try:p.close()
   except Exception as e:result.setdefault('cleanup_errors',[]).append(str(e))
  for s in sessions:
   try:s.close()
   except Exception as e:result.setdefault('cleanup_errors',[]).append(str(e))
  save(trial/'verdict.json',result)
 completed.append(result);save(out/'results.json',completed);print('END',name,result['status'],flush=True)
 if result['status'] in ['FAIL','INCONCLUSIVE'] or result.get('cleanup_errors'):
  save(out/'status.json',{'state':'STOPPED','reason':result,'completed':len(completed),'total':40,'utc':time.time()});raise SystemExit(1)
save(out/'status.json',{'state':'COMPLETE','completed':40,'total':40,'overall':'INCONCLUSIVE if kernel execution was rejected before GPU; inspect per-path verdicts','utc':time.time()})
