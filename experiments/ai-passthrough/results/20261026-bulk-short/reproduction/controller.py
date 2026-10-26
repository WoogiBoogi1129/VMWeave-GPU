import subprocess,json,time,sys,fcntl
from pathlib import Path
B=Path(__file__).resolve().parent;O=Path('experiments/ai-passthrough/results/20261026-bulk-short');lock=(B/'run.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
manifest=json.loads((O/'manifest.json').read_text())
def status(state,**extra):
 manifest.update(status=state,updated_unix=time.time(),**extra);(O/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
try:
 for label,modes in [('copy',['off','on']),('r1',['flyt','off','on']),('r2',['off','on','flyt']),('r3',['on','flyt','off'])]:
  for mode in modes:
   status('RUNNING',active=[label,mode]);print('START',label,mode,flush=True)
   with (B/f'{label}-{mode}.log').open('w') as f:subprocess.run([sys.executable,'-u',str(B/'run_session.py'),mode,label],stdout=f,stderr=subprocess.STDOUT,check=True)
   print('DONE',label,mode,flush=True)
 status('MEASUREMENTS_COMPLETE_ANALYSIS_PENDING',active=None)
except BaseException as e:
 status('STOPPED',error=repr(e));raise
