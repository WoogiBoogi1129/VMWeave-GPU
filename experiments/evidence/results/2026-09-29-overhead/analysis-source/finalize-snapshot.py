import os,subprocess,time,shutil
from pathlib import Path
b=Path('.local/overhead-20260929');o=Path('experiments/evidence/results/2026-09-29-overhead')
end=time.monotonic()+600
while not (o/'additional-native/r4-N/packing.json').exists():
 if time.monotonic()>end:raise TimeoutError('additional packing')
 time.sleep(1)
print('ADDITIONAL_PACKING_READY',flush=True)
subprocess.run(['taskset','-c','48-51','.local/evidence-venv/bin/python','experiments/evidence/analyze_overhead.py',str(o/'additional-native'),'--cpu',str(b/'cpu.jsonl')],check=True)
subprocess.run(['python3','experiments/evidence/verify_overhead.py',str(o)],check=True)
while not (o/'final-audit.json').exists():
 if 'Traceback' in (b/'publication-cleanup.log').read_text():raise RuntimeError('cleanup failed; inspect log')
 if time.monotonic()>end:raise TimeoutError('resource audit')
 time.sleep(1)
subprocess.run(['python3','experiments/evidence/report_overhead.py',str(o)],check=True)
subprocess.run(['python3',str(b/'update-docs.py')],check=True)
for name in ['analyze_overhead.py','verify_overhead.py','report_overhead.py','overhead_terminal_table.py']:shutil.copy2(Path('experiments/evidence')/name,o/'analysis-source'/name)
env=os.environ.copy();env['NODE_PATH']=str(Path('.local/evidence-20260924/tools/node_modules').resolve())
subprocess.run(['taskset','-c','48-51','node','scripts/capture-overhead-static.cjs',str(o),str(b)],env=env,check=True)
print('SNAPSHOT_REPORT_AND_TERMINAL_READY',flush=True)
