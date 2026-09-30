"""Continue only after the running overhead stage succeeds; collect between stages."""
import os,subprocess,time
from common import *
def collect(stage):
 commands=[['python3','experiments/performance/export_telemetry.py'],
  ['taskset','-c','48-51','.local/evidence-venv/bin/python','experiments/performance/verify.py',str(OUT)],
  ['taskset','-c','48-51','.local/evidence-venv/bin/python','experiments/performance/analyze.py',str(OUT)],
  ['taskset','-c','48-51','.local/evidence-venv/bin/python','experiments/performance/plot.py',str(OUT)],
  ['python3','experiments/performance/annotate_grafana.py'],
  ['taskset','-c','48-51','node','experiments/performance/capture_grafana.cjs',str(OUT),str(BASE),stage]]
 for i,cmd in enumerate(commands):
  with (BASE/f'collect-{stage}-{i}.txt').open('w') as log:
   subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True,env={**os.environ,'NODE_PATH':str(ROOT/'.local/evidence-20260924/tools/node_modules')})
while not (OUT/'overhead-complete.json').exists():
 if list((OUT/'runs').glob('perf-o-*/failure.json')):raise RuntimeError('Overhead stage failed; inspect original evidence')
 time.sleep(10)
collect('o')
for stage,letter in [('single','c'),('shared','d')]:
 with (BASE/(stage+'-driver.txt')).open('w') as log:
  subprocess.run(['script','-q','-f','-e','-c','python3 experiments/performance/run.py '+stage,str(BASE/(stage+'.terminal'))],stdout=log,stderr=subprocess.STDOUT,check=True)
 collect(letter)
save(OUT/'campaign-execution-complete.json',{'utc':time.time(),'stages':['overhead','single','shared'],'status':'Executed and independently verified; see enforcement outcomes separately'})
