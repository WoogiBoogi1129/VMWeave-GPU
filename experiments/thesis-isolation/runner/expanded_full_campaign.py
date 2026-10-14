"""10 fresh pairs, 30 x 1260s; preserve prior pilots and stop on failures."""
from common import *
import sys,fcntl,hashlib,csv,datetime,statistics
lock=(BASE/'expanded-pair.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
stamp=time.strftime('%Y%m%d%H%M%S',time.gmtime());out=OUT/('expanded-full-'+stamp);out.mkdir()
review=json.loads((OUT/'expanded-pair-20261013124130/telemetry-review.json').read_text());assert review['review']=='PASS'
plan=[{'rep':r,'direction':d,'name':f'iso-wide-r{r}-{d}-{stamp}','seed':20261013+r*100+(d=='ba')} for r in range(1,6) for d in ['ab','ba']]
paths=['runner/expanded_pair_full.py','runner/expanded_full_campaign.py','runner/e2.py','runner/session.py','runner/common.py','probes/load_calibration_expanded.py']
hashes={p:hashlib.sha256((ROOT/'experiments/thesis-isolation'/p).read_bytes()).hexdigest() for p in paths}
save(out/'protocol.json',{'plan':plan,'seconds_each':1260,'target_requests':10000,'pilots_counted':False,'source_commit':call(['git','rev-parse','HEAD']).strip(),'tool_sha256':hashes,'load':{'memory_mib':1024,'matrix_dimension':8192,'batch':128},'scope':'Strong compute and expanded memory load; no DRAM saturation claim','automatic_duration_extension':False,'telemetry_review':review})
print('OUTPUT',out,flush=True);completed=[];allrows=[];activity=[]
try:
 for job in plan:
  for path,h in hashes.items():assert hashlib.sha256((ROOT/'experiments/thesis-isolation'/path).read_bytes()).hexdigest()==h,'Tool changed during campaign'
  save(out/'status.json',{'state':'RUNNING','current':job,'completed_runs':len(completed),'total_runs':10,'utc':time.time()})
  print('RUN_START',job['name'],flush=True)
  with (out/(job['name']+'.log')).open('x') as log:
   rc=subprocess.run([sys.executable,ROOT/'experiments/thesis-isolation/runner/expanded_pair_full.py','--name',job['name'],'--direction',job['direction'],'--seed',str(job['seed'])],stdout=log,stderr=subprocess.STDOUT).returncode
  p=OUT/'pairs'/job['name']
  if rc or (p/'failure.json').exists():raise RuntimeError('Run failed: '+job['name'])
  assert json.loads((p/'status.json').read_text())['state']=='MEASUREMENT_COMPLETE'
  for slot in ['a','b']:
   d=OUT/'runs'/(job['name']+'-'+slot)
   assert json.loads((d/'cleanup.json').read_text())['released']
   assert not (d/'cleanup-error.json').exists() and not (d/'probe-close-error.json').exists()
  rows=json.loads((p/'results.json').read_text());assert len(rows)==3 and all(r['errors']==0 and r['mismatches']==0 and r['elapsed_s']>=1260 for r in rows)
  samples=[];tz=datetime.timezone(datetime.timedelta(hours=9))
  for row in csv.DictReader((p/'gpu-samples.csv').open()):
   row={k.strip():v.strip() for k,v in row.items()}
   t=datetime.datetime.strptime(row['timestamp'],'%Y/%m/%d %H:%M:%S.%f').replace(tzinfo=tz).timestamp()
   samples.append((t,float(row['utilization.gpu [%]'].split()[0]),float(row['utilization.memory [%]'].split()[0])))
  for row in rows:
   ev=json.loads((p/(row['condition']+'-observer.json')).read_text());req=[r for r in ev if r['event']=='request'];a=req[0]['received_host_utc'];z=ev[-1]['received_host_utc']
   ss=[s for s in samples if a+1<=s[0]<=z-1];assert len(ss)>=.9*1260,'Insufficient GPU samples'
   activity.append({'trial':job['name'],'condition':row['condition'],'samples':len(ss),'gpu_mean_pct':statistics.mean(s[1] for s in ss),'memory_activity_mean_pct':statistics.mean(s[2] for s in ss)})
   allrows.append({'trial':job['name'],'repetition':job['rep'],'direction':job['direction'],**row})
  completed.append(job);save(out/'completed.json',completed);save(out/'results.json',allrows);save(out/'activity.json',activity);print('RUN_COMPLETE',job['name'],flush=True)
 save(out/'status.json',{'state':'COMPLETE','completed_runs':10,'conditions':30,'utc':time.time(),'service_suitability':'INCONCLUSIVE','publishing_started':False})
except Exception as e:
 save(out/'status.json',{'state':'STOPPED','error':str(e),'completed_runs':len(completed),'utc':time.time()});raise
