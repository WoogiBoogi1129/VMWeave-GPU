"""Stage 4 pilot using the existing, warmed, stage-3 MLP sessions.
The stage-3 owner is idle: submit only the supported observe command via its
SSH child's stdin pipe. Keep all original event logs and save separate copies.
"""
import json, math, os, pathlib, statistics, subprocess, time
ROOT=pathlib.Path(__file__).resolve().parents[3]
state=json.loads((ROOT/'.local/thesis-isolation-20261012/e2-prepared-pair.json').read_text())
prep=pathlib.Path(state['preparation'])
status=json.loads((prep/'stage3/status.json').read_text())
assert status['status']=='PASS' and status['idle_until_utc']>time.time()+240
out=prep/'stage4';out.mkdir(exist_ok=False)
def save(name,value):
 (out/name).write_text(json.dumps(value,indent=2)+'\n')
def read_events(p):
 rows=[]
 for line in p.read_text().splitlines():
  try:rows.append(json.loads(line))
  except json.JSONDecodeError:pass
 return rows
owners=[]
for p in pathlib.Path('/proc').glob('[0-9]*'):
 try:
  args=(p/'cmdline').read_bytes().split(b'\0')
  if len(args)>1 and args[0].endswith(b'python3') and args[1].endswith(b'/validate_e2_workload.py'):owners.append(p)
 except (OSError,PermissionError):pass
assert len(owners)==1,owners
owner=owners[0];children=(owner/'task'/owner.name/'children').read_text().split()
records=[]
try:
 for row in state['sessions']:
  matches=[]
  for pid in children:
   p=pathlib.Path('/proc')/pid;args=(p/'cmdline').read_bytes().decode().split('\0')
   if args[0]=='ssh' and 'ubuntu@'+row['ip'] in args and '/tmp/perf/mlp.py' in args[-2]:matches.append(p)
  assert len(matches)==1,matches
  p=matches[0];assert os.readlink(p/'fd/0').startswith('pipe:')
  channel=json.loads(subprocess.check_output(['kubectl','-n',row['namespace'],'get','sharedmemorychannels.vmweave.io',row['name'],'-o','json']))
  assert channel['metadata']['uid']==row['channel_uid'] and channel['status']['phase']=='Ready'
  log=pathlib.Path(row['out'])/'stage3/requests-events.jsonl';before=read_events(log)
  assert before[-1]['event']=='ready', 'Refuse repeated or overlapping pilot'
  save('progress.json',{'vm':row['name'],'state':'MEASURING','started_utc':time.time(),'duration_s':30})
  with (p/'fd/0').open('w') as stream:stream.write('observe 30\n');stream.flush()
  end=time.monotonic()+80
  while True:
   new=read_events(log)[len(before):]
   if new and new[-1]['event']=='done':break
   if time.monotonic()>end:raise TimeoutError('Pilot completion deadline exceeded')
   time.sleep(1)
  save(row['slot']+'-events.json',new)
  req=[r for r in new if r['event']=='request'];done=new[-1]
  assert req and all(r['code']==0 for r in req),'Pilot request error or mismatch'
  assert done['attempts']==len(req)
  latency=sorted(r['latency_s'] for r in req);rate=len(req)/done['elapsed_s']
  rec={'vm':row['name'],'completed':len(req),'elapsed_s':done['elapsed_s'],'throughput_rps':rate,'p99_latency_s_exploratory':latency[math.ceil(.99*len(latency))-1],'errors':0,'mismatches':0,'max_abs_error':max(r['max_abs_error'] for r in req),'seconds_for_10000_estimated':10000/rate}
  records.append(rec);save('results.json',records);print('PILOT_COMPLETE',json.dumps(rec),flush=True)
 duration=max(180,math.ceil(max(r['seconds_for_10000_estimated'] for r in records)*1.25/60)*60)
 save('measurement-plan.json',{'status':'PILOT_COMPLETE','scope':'User-selected original performance step 4; separate from renumbered isolation E2','pilot_seconds_per_direction':30,'minimum_condition_seconds':180,'target_completed_per_condition':10000,'selected_condition_seconds':duration,'headroom_fraction':.25,'duration_basis':'Slower of two idle-peer pilots, plus 25%, rounded up to minutes','contended_rate_measured':False,'sample_target_guaranteed':False,'sample_rule':'Use same fixed duration for all conditions; report actual counts. If below 10000, disclose shortfall and p99 uncertainty. Do not selectively extend conditions.','p99_limitation':'Pilot p99 is exploratory; only about 1% of completed requests inform the upper tail. Correlated samples further reduce precision.','latency_scope':'GPU forward and synchronization; correctness transfer/comparison excluded from latency but included in throughput elapsed time','next_step_started':False,'records':records})
 print('STAGE4_COMPLETE condition_seconds='+str(duration),flush=True)
except Exception as e:
 save('failure.json',{'error':str(e),'utc':time.time()});raise
