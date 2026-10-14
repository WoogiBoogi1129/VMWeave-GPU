"""E2 stage 4: paired synthetic buffers through unchanged registered-pointer path."""
from campaign import *
import hashlib

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
class TracedSession(Session):
 def command(self,program,args):
  return [part.replace('FLYT_TRACE_REQUESTS=0','FLYT_TRACE_REQUESTS=1') for part in super().command(program,args)]

name='iso-cross-boundary-'+time.strftime('%Y%m%d%H%M%S',time.gmtime())
out=OUT/name;out.mkdir();sessions=[];probes=[];events=[];failure=None
build=json.loads((BASE/'boundary-build/image.json').read_text());IMAGES['worker']=build['image']
save(out/'build.json',build);print('OUTPUT',out,flush=True)
save(out/'status.json',{'state':'PREPARING','utc':time.time(),'scope':'paired synthetic buffers, registered-pointer path'})

def command(p,op,event):
 rows=p.command(op);events.append({'vm':p.s.name,'command':op,'rows':rows});save(out/'events.json',events)
 return next(x for x in rows if x['event']==event)
def check(p):
 x=command(p,'check','check');assert x['code']==0 and x['mismatches']==0,x

def identity(s):
 script=r'''
import os,json,sys
from pathlib import Path
uid=sys.argv[1];rows=[]
for p in Path('/proc').glob('[0-9]*'):
 try:
  cg=(p/'cgroup').read_text()
  if uid not in cg and uid.replace('-','_') not in cg:continue
  exe=os.readlink(p/'exe')
  if exe!='/opt/flyt/bin/flyt-shm-worker.original':continue
  env=dict(x.split('=',1) for x in (p/'environ').read_bytes().decode().split(chr(0)) if '=' in x)
  maps=(p/'maps').read_text()
  rows.append({'host_pid':int(p.name),'exe':exe,'start_ticks':(p/'stat').read_text().rsplit(')',1)[1].split()[19],
   'status_nspid':[x for x in (p/'status').read_text().splitlines() if x.startswith('NSpid:')],
   'environment':{k:v for k,v in env.items() if k in ['LD_PRELOAD','FLYT_GPU_UUID','FLYT_RESOURCE_BACKEND','FLYT_MEMORY_BYTES','CUDA_MPS_PIPE_DIRECTORY','FLYT_TRACE_REQUESTS']},
   'libraries':sorted(set(x.split()[-1] for x in maps.splitlines() if any(y in x for y in ['libcuda','libvgpu','context-observer'])))})
 except (OSError,UnicodeDecodeError):continue
assert len(rows)==1,rows
print(json.dumps(rows[0]))
'''
 uid=s.get('pod',s.worker)['metadata']['uid']
 result=json.loads(k('exec','-i','-n',NS,HELPER,'--','chroot','/host','python3','-',uid,input=script));save(s.out/'process-identity.json',result);return result

try:
 ensure_admin()
 assert GPU not in call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
 for i,slot in enumerate(['a','b']):
  s=TracedSession(name+'-'+slot,slot=slot,memory=2048,cap=50);s.profile_name='isolation-boundary-trace-v2-20261014';sessions.append(s);s.prepare()
  call(s.scp+[BASE/'artifacts/cross-boundary','ubuntu@'+s.ip+':/tmp/perf/cross-boundary'])
 for i,s in enumerate(sessions):
  p=Probe(s,202610140+i*100,program='cross-boundary');probes.append(p);freeze(s)
  print('READY',s.slot,flush=True)
 identities=[identity(s) for s in sessions]
 assert identities[0]['host_pid']!=identities[1]['host_pid']
 for row in identities:
  assert row['environment']['FLYT_GPU_UUID']==GPU
  assert row['environment']['FLYT_RESOURCE_BACKEND']=='hami'
  assert 'CUDA_MPS_PIPE_DIRECTORY' not in row['environment']
  assert any('libvgpu.so' in x for x in row['libraries'])
  assert any('context-observer.so' in x for x in row['libraries'])
 save(out/'ownership.json',[{'vm':p.s.name,'namespace':p.s.ns,'worker':p.s.worker,'channel_uid':p.s.uid,'buffer':p.ready,'process':identities[i]} for i,p in enumerate(probes)])
 save(out/'status.json',{'state':'REGISTERED_POINTER_PILOT','utc':time.time()})
 for p in probes:
  check(p)
  r=command(p,'read','access');assert all(r[k]==0 for k in ['prep','launch','sync','copy']) and r['observed']==r['expected'],r
 cross_results=[]
 for requester,target in [(probes[1],probes[0]),(probes[0],probes[1])]:
  for op in ['cross_read','cross_write']:
   check(target);check(requester)
   r=command(requester,op+' '+str(target.ready['address']),'cross')
   cross_results.append({'requester':requester.s.name,'target_vm':target.s.name,'target_buffer':target.ready,'observation':r})
   save(out/'cross-attempts.json',cross_results)
   check(target);check(requester)
   assert r['prep']==0 and r['local_lookup']!=0 and r['launch']==1 and r['sync']==-1 and not r['read_valid'],('Unexpected path; stop pilot',r)
 inventory=call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader']);(out/'gpu-processes.txt').write_text(inventory)
 for row in identities:assert any(GPU in line and str(row['host_pid'])==line.split(',')[1].strip() for line in inventory.splitlines())
 for p in probes:p.close()
 probes=[]
 trace_summary=[]
 for s in sessions:
  worker=k('logs','-n',s.ns,s.worker);(s.out/'worker-trace.txt').write_text(worker)
  guest=(s.out/'probe-stderr.txt').read_text()
  parsed=[];contexts=[]
  for log in [guest,worker]:
   for line in log.splitlines():
    if line.startswith('FLYT_TRACE '):parsed.append(json.loads(line[len('FLYT_TRACE '):]))
    if line.startswith('BOUNDARY_CONTEXT '):contexts.append(json.loads(line[len('BOUNDARY_CONTEXT '):]))
  grouped={}
  for r in parsed:
   key=(r['allocation'],r['generation'],r['session_id'],r['request_id'])
   grouped.setdefault(key,{})[(r['role'],r['event'])]=r
  for key,rows in grouped.items():
   assert set(rows)=={('guest','submit'),('guest','receive'),('worker','take'),('worker','respond')},(key,list(rows))
   assert len({x['api_id'] for x in rows.values()})==1
   for endpoint in ['guest','worker']:
    r=rows[(endpoint,'receive' if endpoint=='guest' else 'respond')]
    assert r['transport_status']==0 and r['api_result']==0,r
  launches=[rows for rows in grouped.values() if rows[('guest','submit')]['api_id']==0x2033]
  assert len(launches)==1 and len(contexts)==1,(len(launches),len(contexts))
  assert all(x['context_query']==0 and x['context'] not in ['(nil)','0x0'] and x['launch']==0 for x in contexts)
  assert len({(x['pid'],x['context']) for x in contexts})==1
  summary={'vm':s.name,'complete_request_chains':len(grouped),'kernel_launches':len(launches),'contexts':contexts}
  trace_summary.append(summary);save(s.out/'trace-summary.json',summary)
 save(out/'result.json',{'status':'REGISTERED_PATH_REJECTED_BEFORE_SUBMIT','sessions':[s.name for s in sessions],'trace_summary':trace_summary,
  'cross_requests_attempted':4,'cross_gpu_access_executed':False,'cross_results':cross_results,'residual_data_tested':False,'gpu_boundary_proven':False,
  'sharing_scope':'dedicated per-process CUDA contexts; no sharing API called by this probe; not a global sharing audit',
  'probe_sha256':digest(BASE/'artifacts/cross-boundary')})
 print('REGISTERED_PATH_REJECTED_BEFORE_SUBMIT',flush=True)
except Exception as e:
 failure=repr(e);save(out/'failure.json',{'error':failure,'utc':time.time()});print('FAILED',failure,flush=True)
finally:
 errors=[]
 for p in probes:
  try:p.close()
  except Exception as e:errors.append(repr(e))
 for s in sessions:
  try:
   if getattr(s,'worker',None) and not (s.out/'worker-trace.txt').exists():
    (s.out/'worker-trace.txt').write_text(k('logs','-n',s.ns,s.worker,check=False))
   s.close()
  except Exception as e:errors.append(repr(e))
 save(out/'status.json',{'state':'CLOSED' if not errors else 'CLEANUP_ERROR','failure':failure,'cleanup_errors':errors,'utc':time.time()})
 print('CLOSED',errors,flush=True)
 if failure or errors:sys.exit(1)
