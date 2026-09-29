"""Frozen C5/C6 measurement matrix, with UID-scoped normal cleanup and resumability.

Run with `script --log-out ... --log-timing ... -c 'python3 -u ...'` to keep
the actual terminal session. Existing completed run IDs are verified, not rerun.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import time
from pathlib import Path
from campaign_runtime import Run,save,GPU,call

p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--stage',choices=['reference-b','measure'],required=True);a=p.parse_args();base=a.base.resolve()

def finished(name):
 d=base/'runs'/name
 if not d.exists():return False
 if not (d/'metrics.json').exists() or not (d/'cleanup.json').exists():raise RuntimeError('Incomplete prior run, investigate: '+name)
 m=json.loads((d/'metrics.json').read_text());c=json.loads((d/'cleanup.json').read_text())
 if m['execution']!='PASS' or not c['released']:raise RuntimeError('Prior failed run must retain separate retry ID: '+name)
 return True

def single(name,backend,compute,condition,probe):
 if finished(name):return json.loads((base/'runs'/name/'metrics.json').read_text())['result']
 r=Run(base,name,backend,compute,**condition)
 try:r.prepare();return r.execute(**probe)
 except Exception as e:
  save(r.out/'failure.json',{'error':str(e),'utc_seconds':time.time()});raise
 finally:r.close()

if a.stage=='reference-b':
 hashes=[]
 for n in range(1,4):
  name=f'evidence-c28-refb-{n}'
  single(name,'native-hami-disabled',100,{'phase':'reference','seed':2027},dict(kind='fma',iterations=1048576,seed=2027,seconds=2,output=f'reference-long-b-{n}.bin'))
  hashes.append(hashlib.sha256((base/f'artifacts/reference-long-b-{n}.bin').read_bytes()).hexdigest())
 assert len(set(hashes))==1
 (base/'artifacts/reference-long-b.bin').write_bytes((base/'artifacts/reference-long-b-1.bin').read_bytes());save(base/'reference-long-b-hashes.json',hashes)
 raise SystemExit(0)

# Calibration values are frozen before the first formal measurement.
protocol=base/'protocol.json'
if not protocol.exists():
 rates={}
 for w in ['long','short']:
  d=json.loads((base/f'runs/evidence-c28-cal-{w}-shm/metrics.json').read_text())
  assert d['execution']=='PASS';rates[w]=d['result']['throughput']
 native=json.loads((base/'runs/evidence-c28-cal-long-native-hami-disabled/metrics.json').read_text())['result']['throughput']
 save(protocol,{'created_utc':time.time(),'gpu_uuid':GPU,'fixed_counts':{w:math.ceil(rate*32) for w,rate in rates.items()},
    'overhead_count':math.ceil(max(native,rates['long'])*32),'phase':'formal campaign; memory NUMA observed, not strict binding',
    'c3_c4':'reuse 2026-09-24 evidence; no new 5-repeat C3/C4 campaign',
    'c6_workload':'FMA long; integer microkernel pilot showed extremely short native operations. Use same validated long FMA with 2 MiB input/output for an interpretable fixed-work comparison.',
    'c5_time_repeats':3,'c5_fixed_repeats':5,'c6_repeats':5,'warmup_seconds':10,'time_measure_seconds':60,'interference_seconds':90,
    'limiter_verdict':'NOT_EVALUATED; no verified proportional-utilization contract',
    'preparation':'controller Released-history optimization, same guest shim and Worker as previous campaign'})
cfg=json.loads(protocol.read_text());tasks=[]
for phase,reps in [('time',3),('fixed',5)]:
 for repeat in range(1,reps+1):
  for w,it in [('long',1048576),('short',1024)]:
   for compute in ([100,50,25] if repeat%2 else [25,50,100]):
    name=f'evidence-c28-{phase[0]}-{w[0]}-{compute}-{repeat}'
    probe=dict(kind='fma',iterations=it,reference=f'reference-{w}.bin',seconds=60,count=cfg['fixed_counts'][w] if phase=='fixed' else 0)
    tasks.append({'id':name,'backend':'shm','compute':compute,'condition':{'phase':'C5-'+phase,'repeat':repeat,'workload':w},'probe':probe})
for repeat in range(1,6):
 for mode in ['resident','transfer']:
  for backend in (['native','shm'] if repeat%2 else ['shm','native']):
   tasks.append({'id':f'evidence-c28-ov-{mode[0]}-{backend[0]}-{repeat}','backend':backend,'compute':100,
      'condition':{'phase':'C6-overhead','repeat':repeat,'mode':mode},'probe':dict(kind='fma',mode=mode,iterations=1048576,count=cfg['overhead_count'],reference='reference-long.bin')})
save(base/'run-order.json',tasks)
for task in tasks:
 single(task['id'],task['backend'],task['compute'],task['condition'],task['probe'])

for repeat in range(1,6):
 for mode in ['resident','transfer']:
  for group in (['a','b','pair'] if repeat%2 else ['pair','b','a']):
   slots=['a','b'] if group=='pair' else [group]
   names=[f'evidence-c28-in-{mode[0]}-{group}-{repeat}-{s}' for s in slots]
   done=[finished(n) for n in names]
   if all(done):continue
   if any(done):raise RuntimeError('Partially completed pair requires a separate retry group')
   runs=[Run(base,n,'shm',50,s,phase='C6-interference',repeat=repeat,mode=mode,group=group) for n,s in zip(names,slots)]
   try:
    with ThreadPoolExecutor(max_workers=2) as pool:
     for f in [pool.submit(r.prepare) for r in runs]:f.result()
     scheduled=time.time()+20
     jobs=[pool.submit(r.execute,kind='fma',mode=mode,seconds=90,iterations=1048576,seed=2026 if r.slot=='a' else 2027,start=scheduled,reference='reference-long.bin' if r.slot=='a' else 'reference-long-b.bin') for r in runs]
     for f in jobs:f.result()
   except Exception as e:
    for r in runs:save(r.out/'failure.json',{'error':str(e),'utc_seconds':time.time()})
    raise
   finally:
    for r in runs:r.close()
save(base/'MEASUREMENTS_COMPLETE.json',{'completed_at':time.time(),'status':'execution matrix completed; independent analysis required'})
