"""Two directions, three 180s conditions each. No automatic full experiment."""
from common import *
import fcntl,sys,math
lock=(BASE/'expanded-pair.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
stamp=time.strftime('%Y%m%d%H%M%S',time.gmtime());out=OUT/('expanded-pair-'+stamp);out.mkdir();allrows=[]
print('OUTPUT',out,flush=True)
try:
 for i,direction in enumerate(['ab','ba']):
  name=f'iso-wide-pilot-{direction}-{stamp}'
  save(out/'status.json',{'state':'RUNNING','direction':direction,'trial':name,'completed_directions':i,'utc':time.time()})
  with (out/(direction+'.log')).open('x') as log:
   rc=subprocess.run([sys.executable,ROOT/'experiments/thesis-isolation/runner/expanded_pair_pilot.py','--name',name,'--direction',direction,'--seed',str(20261013+i)],stdout=log,stderr=subprocess.STDOUT).returncode
  pair=OUT/'pairs'/name
  if rc or (pair/'failure.json').exists():raise RuntimeError('Pilot failed: '+name)
  for slot in ['a','b']:
   p=OUT/'runs'/(name+'-'+slot);assert json.loads((p/'cleanup.json').read_text())['released'] and not (p/'cleanup-error.json').exists()
  for r in json.loads((pair/'results.json').read_text()):allrows.append({'direction':direction,'trial':name,**r})
  save(out/'results.json',allrows);print('DIRECTION_COMPLETE',direction,flush=True)
 rate=min(r['throughput_rps'] for r in allrows);seconds=max(180,math.ceil(10000/rate*1.25/60)*60)
 save(out/'duration-estimate.json',{'suggested_condition_seconds':seconds,'basis':'slowest of 6 paired pilot conditions plus 25%, rounded to minutes','minimum_seconds':180,'target_requests':10000,'target_guaranteed':False,'full_experiment_started':False,'load_telemetry_review_required':True})
 save(out/'status.json',{'state':'COMPLETE','conditions':6,'utc':time.time(),'full_experiment_started':False})
except Exception as e:
 save(out/'status.json',{'state':'STOPPED','error':str(e),'utc':time.time()});raise
