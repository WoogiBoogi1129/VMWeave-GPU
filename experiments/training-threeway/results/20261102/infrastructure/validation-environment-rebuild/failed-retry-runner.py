import sys,subprocess,json,time,traceback
from pathlib import Path
sys.path.insert(0,'experiments/training-threeway')
from lab import O,B,save
from cleanup import cleanup
try:
 print('RETRY_SUPPLEMENTARY_VALIDATION',time.time(),flush=True)
 subprocess.run(['python3','-u','experiments/training-threeway/check_transfers.py'],check=True)
except BaseException:
 traceback.print_exc()
 cleanup()
 raise
cleanup()
subprocess.run(['.local/evidence-venv/bin/python','experiments/training-threeway/analyze.py','--plots'],check=True)
subprocess.run(['python3','experiments/training-threeway/report.py'],check=True)
from validate import validate
save(O/'audit.json',validate(O))
save(B/'postprocess-complete.json',{'utc':time.time(),'passed':True})
print('POSTPROCESS_COMPLETE',flush=True)
