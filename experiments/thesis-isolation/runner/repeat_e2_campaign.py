"""Stage 6: preserve the completed ab repetition, then run nine fresh pairs."""
import fcntl,sys
from common import *
lock=(BASE/'stage6.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
prior='iso-perf-stage5-20261012104353'
out=OUT/'stage6';out.mkdir(exist_ok=False)
def verified(name):
 p=OUT/'pairs'/name
 assert json.loads((p/'status.json').read_text())['state']=='MEASUREMENT_COMPLETE'
 assert not (p/'failure.json').exists()
 rows=json.loads((p/'results.json').read_text())
 assert {r['condition'] for r in rows}=={'baseline','memory','compute'}
 assert all(r['elapsed_s']>=1260 and r['errors']==0 and r['mismatches']==0 for r in rows)
 for slot in ['a','b']:
  d=OUT/'runs'/(name+'-'+slot)
  assert json.loads((d/'cleanup.json').read_text())['released']
  assert not (d/'cleanup-error.json').exists()
 return rows
verified(prior)
plan=[{'repetition':1,'direction':'ab','name':prior,'reused':True}]
for rep in range(1,6):
 for direction in ['ab','ba']:
  if rep==1 and direction=='ab':continue
  plan.append({'repetition':rep,'direction':direction,'name':f'iso-perf-r{rep}-{direction}-20261012','seed':20261012+rep*100+(direction=='ba'),'reused':False})
save(out/'plan.json',{'runs':plan,'seconds_per_condition':1260,'target_runs':10,'target_conditions':30,'source_prior':prior,'scope':'Original performance experiment stage 6'})
completed=[plan[0]]
try:
 for row in plan[1:]:
  save(out/'status.json',{'state':'RUNNING','current':row,'completed_runs':len(completed),'total_runs':10,'utc':time.time()})
  print('RUN_START',json.dumps(row),flush=True)
  with (out/(row['name']+'.log')).open('x') as log:
   p=subprocess.run([sys.executable,ROOT/'experiments/thesis-isolation/runner/measure_e2_repeat.py','--name',row['name'],'--direction',row['direction'],'--seed',str(row['seed'])],stdout=log,stderr=subprocess.STDOUT)
  if p.returncode:raise RuntimeError(f"Run {row['name']} failed ({p.returncode})")
  verified(row['name']);completed.append(row);save(out/'completed.json',completed)
  print('RUN_COMPLETE',row['name'],flush=True)
 save(out/'status.json',{'state':'COMPLETE','completed_runs':10,'total_runs':10,'completed_conditions':30,'utc':time.time(),'stage7_started':False})
except Exception as e:
 save(out/'status.json',{'state':'STOPPED_ERROR','error':str(e),'completed_runs':len(completed),'utc':time.time()});raise
