"""One-pair supplemental E2 pilot, preserving all previous runs."""
from campaign import *
import hashlib, argparse
parser=argparse.ArgumentParser();parser.add_argument("operation",choices=["rawread","rawwrite"]);args=parser.parse_args()
name='iso-absent-'+args.operation+'-'+time.strftime('%Y%m%d%H%M%S',time.gmtime());out=OUT/name;out.mkdir();sessions=[];probes=[];records=[]
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
 intact(a);intact(b)
 assert a.ready['handle']==b.ready['handle']
 own=command(b,f"rawread {b.ready['handle']}",'access');assert own['code']==0 and own['observed']==b.ready['seed']
 extra=command(a,'extra','extra');assert extra['code']==0 and extra['handle']!=b.ready['handle'];save(out/'extra-target.json',extra);intact(a)
 access=command(b,f"{args.operation} {extra['handle']}",'access');intact(a)
 # Record expected session failure separately; it is not a data mismatch.
 followup=command(b,'check','check')
 stderr=(b.s.out/'probe-stderr.txt').read_text()
 result={'status':'OBSERVED','operation':args.operation,'access':access,'target_intact':True,'requester_followup':followup,'guest_stderr':stderr,'gpu_cross_access_verified':False,'expected_rejection_confirmed':access['code']==999 and followup['code']==999 and 'transport_status=3' in stderr}
 save(out/'result.json',result)
 if not result['expected_rejection_confirmed']:raise RuntimeError('Unexpected response; preserve for review')
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
