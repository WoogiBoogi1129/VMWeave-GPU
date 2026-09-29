"""Predeclared replacement for a run affected by a guest wall-clock step."""
import argparse
import time
from pathlib import Path
from campaign_runtime import Run,save

p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);a=p.parse_args()
if not (a.base/'MEASUREMENTS_COMPLETE.json').exists():
    raise SystemExit('Finish the frozen matrix first; never overlap GPU workloads.')
r=Run(a.base,'evidence-c28-t-l-25-1-clockretry','shm',25,phase='C5-time',repeat=1,workload='long',replaces='evidence-c28-t-l-25-1')
try:
    r.prepare();r.execute(kind='fma',iterations=1048576,reference='reference-long.bin',seconds=60)
except Exception as error:
    save(r.out/'failure.json',{'error':str(error),'utc_seconds':time.time()});raise
finally:
    r.close()
