from pathlib import Path
import subprocess,json,time
b=Path('.local/overhead-20260929');o=Path('experiments/evidence/results/2026-09-29-overhead')
while True:
 text=(b/'formal-02.log').read_text()
 if 'CAMPAIGN_COMPLETE' in text:break
 if 'Traceback (most recent call last)' in text:raise RuntimeError('Formal campaign failed; no automatic continuation')
 time.sleep(10)
cmd=['taskset','-c','48-51','.local/evidence-venv/bin/python','experiments/evidence/analyze_overhead.py',str(o),'--cpu',str(b/'cpu.jsonl')]
with (b/'replacement.log').open('w') as log:subprocess.run(['python3','experiments/evidence/run_overhead.py','--base',str(b),'--output',str(o),'--repetitions','7','--condition-mask','1'],stdout=log,stderr=subprocess.STDOUT,check=True)
subprocess.run(cmd,check=True)
d=json.loads((o/'extension-decision.json').read_text());assert d['first_three_complete'];mask=d['condition_mask']
print('EXTENSION_DECISION',json.dumps(d),flush=True)
if mask:
 with (b/'extension.log').open('w') as log:subprocess.run(['python3','experiments/evidence/run_overhead.py','--base',str(b),'--output',str(o),'--repetitions','4,5,6','--condition-mask',str(mask)],stdout=log,stderr=subprocess.STDOUT,check=True)
subprocess.run(cmd+['--plots'],check=True)
print('ALL_MEASUREMENTS_AND_ANALYSIS_COMPLETE',time.time(),flush=True)
