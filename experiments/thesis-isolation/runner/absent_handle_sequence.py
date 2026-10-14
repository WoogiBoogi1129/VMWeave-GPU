"""Two independent pilot pairs. No statistical repetition or GPU fault injection."""
import subprocess,sys,json,time,fcntl
from common import *
lock=(BASE/'absent-handle.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
out=OUT/('absent-sequence-'+time.strftime('%Y%m%d%H%M%S',time.gmtime()));out.mkdir();print('OUTPUT',out,flush=True)
for op in ['rawread','rawwrite']:
 save(out/'status.json',{'state':'RUNNING','operation':op,'utc':time.time()})
 before=set(OUT.glob('iso-absent-'+op+'-*'))
 with (out/(op+'.log')).open('x') as log:rc=subprocess.run([sys.executable,ROOT/'experiments/thesis-isolation/runner/absent_handle_pilot.py',op],stdout=log,stderr=subprocess.STDOUT).returncode
 new=set(OUT.glob('iso-absent-'+op+'-*'))-before
 assert len(new)==1
 trial=new.pop();status=json.loads((trial/'status.json').read_text())
 if rc or (trial/'failure.json').exists() or status['cleanup_errors']:
  save(out/'status.json',{'state':'STOPPED','trial':str(trial),'operation':op,'utc':time.time()});raise SystemExit(1)
 print('COMPLETE',op,trial,flush=True)
save(out/'status.json',{'state':'COMPLETE','trials':2,'utc':time.time()})
