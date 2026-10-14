"""One-pair supplemental E2 pilot, preserving all previous runs."""
from campaign import *
import hashlib
name='iso-access-pilot-'+time.strftime('%Y%m%d%H%M%S',time.gmtime());out=OUT/name;out.mkdir();sessions=[];probes=[];records=[]
def command(p,line,event):
 rows=p.command(line);records.append({'vm':p.s.name,'command':line,'rows':rows});save(out/'events.json',records)
 return next(x for x in rows if x['event']==event)
def intact(p):
 assert command(p,'check','check')['code']==0,'Buffer mismatch or check failure'
def snapshot(p,first):
 x=command(p,'snapshot','snapshot');assert x['code']==0 and x['first']==first and x['rest_mismatches']==0,x
save(out/'status.json',{'state':'PREPARING','scope':'one-pair pilot','utc':time.time()});print('OUTPUT',out,flush=True)
try:
 inv=call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader']);assert GPU not in inv
 for i,slot in enumerate(['a','b']):
  s=Session(name+'-'+slot,slot=slot,memory=2048,cap=50);sessions.append(s);s.prepare()
  call(s.scp+[BASE/'artifacts/access-pilot','ubuntu@'+s.ip+':/tmp/perf/access-pilot'])
  p=Probe(s,202610130+i*100,program='access-pilot');probes.append(p);freeze(s)
 a,b=probes;save(out/'targets.json',{'a':a.ready,'b':b.ready,'probe_sha256':hashlib.sha256((BASE/'artifacts/access-pilot').read_bytes()).hexdigest()})
 intact(a);intact(b);snapshot(b,b.ready['seed'])
 assert command(b,f"read {b.ready['address']}",'access')['launch']==0
 assert command(b,f"write {b.ready['address']}",'access')['launch']==0
 snapshot(b,0xdeadbeef);intact(a);assert command(b,'reset','reset')['code']==0;intact(b)
 assert a.ready['handle']==b.ready['handle']
 x=command(b,f"rawread {a.ready['handle']}",'access');assert x['code']==0 and x['observed']==b.ready['seed']
 assert command(b,f"rawwrite {a.ready['handle']}",'access')['code']==0
 snapshot(b,0xdeadbeef);intact(a);assert command(b,'reset','reset')['code']==0;intact(b)
 extra=command(a,'extra','extra');assert extra['code']==0 and extra['handle']!=b.ready['handle'];save(out/'extra-target.json',extra);intact(a)
 for op in ['rawread','rawwrite']:
  x=command(b,f"{op} {extra['handle']}",'access');intact(a);intact(b)
  assert x['code']!=0,'Unexplained success on absent requester handle'
 for op in ['read','write']:
  x=command(b,f"{op} {extra['address']}",'access');intact(a);intact(b)
  assert x['launch']!=0,'Kernel path changed; preserve evidence for review'
 save(out/'result.json',{'status':'PILOT_COMPLETE','same_handle_own_write_verified':True,'absent_handle_read_write_rejected':True,'own_kernel_read_write_positive_control':True,'target_buffers_intact':True,'gpu_cross_access_verified':False,'rejection_layer':'not independently instrumented','repeat_started':False})
 print('PILOT_COMPLETE',flush=True)
except Exception as e:
 save(out/'failure.json',{'error':str(e),'utc':time.time()});print('PILOT_STOP',str(e),flush=True)
finally:
 errors=[]
 for p in probes:
  try:p.close()
  except Exception as e:errors.append(str(e))
 for s in sessions:
  try:s.close()
  except Exception as e:errors.append(str(e))
 save(out/'status.json',{'state':'CLOSED' if not errors else 'CLEANUP_ERROR','cleanup_errors':errors,'result_exists':(out/'result.json').exists(),'utc':time.time()})
