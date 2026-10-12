"""Stage 3: validate each prepared VM, then keep sessions idle for next step."""
from e2 import *
state=json.loads((BASE/'e2-prepared-pair.json').read_text())
out=Path(state['preparation'])/'stage3';out.mkdir(exist_ok=False)
validate()
probes=[];sessions=[];records=[]
try:
 for row in state['sessions']:
  s=Session.__new__(Session)
  s.__dict__.update(name=row['name'],ns=row['namespace'],slot=row['slot'],memory=2048,cap=50,path='S',uid=row['channel_uid'],ip=row['ip'],bdf=row['bdf'],worker=row['worker'],ssh=row['ssh'],scp=row['scp'],out=Path(row['out'])/'stage3',art=BASE/'artifacts',offset=row['clock_offset'])
  s.out.mkdir(exist_ok=False);sessions.append(s)
  c=s.get(CHAN,s.name)
  if c['metadata']['uid']!=s.uid or c['status']['phase'] not in ['Bound','Ready']:raise RuntimeError('Prepared session no longer usable')
  (s.out/'guest-python.txt').write_text(call(s.ssh+['python3 --version']))
  (s.out/'guest-space.txt').write_text(call(s.ssh+['df -B1 /']))
  p=MLP(s);probes.append(p);freeze(s)
  assert p.ready['torch']=='2.11.0+flyt.cu128' and p.ready['checks']==50
  assert p.ready['max_latency_s']<40
  records.append({'vm':s.name,'namespace':s.ns,**p.ready})
  save(out/'progress.json',records);print('VM_VALIDATED',s.name,p.ready,flush=True)
 save(out/'status.json',{'status':'PASS','workload':'FP32 eager inference MLP 1024-2048-1024 batch 32 seed 20261012','accuracy_rule':{'rtol':1e-4,'atol':1e-6,'reference':'CPU FP32 same weights/input, every output element'},'request_timeout_s':40,'memory_mib_each':2048,'measurement_started':False,'records':records,'idle_until_utc':time.time()+3600})
 print('STAGE3_PASS_IDLE',flush=True)
 # Keep guest library heartbeats alive without GPU load; explicit stop marker or one-hour expiry.
 end=time.monotonic()+3600
 while time.monotonic()<end and not (out/'stop').exists():
  if any(p.p.poll() is not None for p in probes):raise RuntimeError('Idle guest process exited')
  time.sleep(2)
except Exception as e:
 save(out/'failure.json',{'error':str(e),'utc':time.time()});print('STAGE3_ERROR',str(e),flush=True)
finally:
 for p in probes:
  try:p.close()
  except Exception as e:print('PROBE_CLOSE_ERROR',str(e),flush=True)
 for s in sessions:
  try:s.close()
  except Exception as e:save(s.out/'cleanup-error.json',{'error':str(e)})
 save(out/'closed.json',{'utc':time.time()})
