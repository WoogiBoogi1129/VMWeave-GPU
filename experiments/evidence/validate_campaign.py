"""Independent checks of the completed measurement matrix and its evidence."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--tables',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
rows=list(csv.DictReader((a.tables/'runs.csv').open()));primary=[r for r in rows if r['primary']=='True']
checks=[]
def check(name,condition,details=None):checks.append({'check':name,'passed':bool(condition),'details':details})
counts=Counter(r['phase'] for r in primary)
check('primary matrix count',counts=={'C5-time':18,'C5-fixed':30,'C6-overhead':20,'C6-interference':40},dict(counts))
for phase,n in [('C5-time',3),('C5-fixed',5)]:
    got=Counter((r['workload'],int(r['compute'])) for r in primary if r['phase']==phase)
    expected={(w,c):n for w in ['long','short'] for c in [25,50,100]}
    check(phase+' repetitions per condition',got==expected,{str(k):v for k,v in got.items()})
got=Counter((r['mode'],r['backend']) for r in primary if r['phase']=='C6-overhead')
check('C6 overhead repetitions per condition',got=={(m,b):5 for m in ['resident','transfer'] for b in ['native','shm']})
got=Counter((r['mode'],r['group'],r['slot']) for r in primary if r['phase']=='C6-interference')
check('C6 interference repetitions per condition',got=={(m,g,s):5 for m in ['resident','transfer'] for g,s in [('a','a'),('b','b'),('pair','a'),('pair','b')]})
check('all outputs checked and correct',all(r['accuracy_valid']=='True' and int(r['checked_elements'])==524288 for r in rows),len(rows))
check('all completed runs released',all(r['released']=='True' for r in rows))
check('primary GPU alignment and coverage',all(r['gpu_alignment_valid']=='True' and float(r['gpu_sample_coverage_fraction'])>=.95 for r in primary))
check('time tests at least 60 s',all(float(r['elapsed_seconds'])>=60 for r in primary if r['phase']=='C5-time'))
check('fixed count selected before measurement',all(int(r['completed'])==({'long':1678,'short':11339}[r['workload']] if r['phase']=='C5-fixed' else 1819) for r in primary if r['phase'] in ['C5-fixed','C6-overhead']))
check('fixed-work measurements at least 30 s',all(float(r['elapsed_seconds'])>=30 for r in primary if r['phase'] in ['C5-fixed','C6-overhead']))
check('common interference window is valid',all(r['window_active_valid']=='True' and r['chunk_window_valid']=='True' for r in primary if r['phase']=='C6-interference'))
libraries=set();bad_environment=[];bad_affinity=[];missing=[]
for row in primary:
    d=a.base/'runs'/row['run_id']
    if not (d/'runtime-libraries.json').exists():missing.append(row['run_id']);continue
    processes=json.loads((d/'runtime-libraries.json').read_text())
    if len(processes)!=1:missing.append(row['run_id']);continue
    proc=processes[0];env=proc['environment']
    if env.get('CUDA_DEVICE_MEMORY_LIMIT_0')!='4096m' or env.get('CUDA_DEVICE_SM_LIMIT')!=row['compute'] or env.get('GPU_CORE_UTILIZATION_POLICY') is not None:bad_environment.append(row['run_id'])
    expected='0-7' if row['backend']=='native' else ('16-19' if row['slot']=='a' else '20-23')
    if not any(s=='Cpus_allowed_list:\t'+expected for s in proc['affinity_status']):bad_affinity.append(row['run_id'])
    libraries.add(tuple(sorted(proc['library_hashes'].items())))
check('same native/Worker CUDA and HAMi library hashes',len(libraries)==1 and not missing,{'unique_sets':len(libraries),'missing':missing})
check('actual memory/compute/policy environment',not bad_environment,bad_environment)
check('actual native/Worker CPU affinity',not bad_affinity,bad_affinity)
mappings=list(csv.DictReader((a.tables/'gpu-process-mapping.csv').open()))
mapped={r['run_id'] for r in mappings if r['matches_requested_gpu']=='True'}
check('every primary run observed on target GPU',all(r['run_id'] in mapped for r in primary))
check('no mapped PID on an unexpected GPU',all(r['matches_requested_gpu']=='True' for r in mappings))
analysis=json.loads((a.tables/'analysis-status.json').read_text())
check('no unrelated compute process observed on target GPU during primary measurements',analysis['unexpected_gpu_process_samples']==0,analysis['unexpected_gpu_process_samples'])
for name,expected in [('overhead-pairs.csv',10),('interference-pairs.csv',20),('sharing-overlap.csv',10)]:
    file=a.tables/name
    check(name+' row count',file.exists() and len(list(csv.DictReader(file.open())))==expected)
result={'status':'PASS' if all(c['passed'] for c in checks) else 'FAIL','checks':checks,
        'scope':'Measured execution/accuracy/conditions/window validation. Limiter guarantee, strict memory NUMA, API latency and omitted C4 handoff are not validated.'}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
raise SystemExit(0 if result['status']=='PASS' else 1)
