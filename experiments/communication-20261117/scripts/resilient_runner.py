"""Transient user service supervisor; no benchmark parameter changes."""
from common import *
from cleanup import stop_active
import sys
def release():
 for p in B.glob('*-observer.jsonl'):p.with_suffix('.stop').touch()
 (B/'numa.stop').touch()
 if get('namespace',NS):stop_active()
def state(status,**extra):
 save(O/'evidence/supervisor-state.json',{'utc':time.time(),'status':status,'unit':'vmweave-comm-20261117.service',**extra})
def main():
 (B/'numa.stop').unlink(missing_ok=True)
 state('measurement_running')
 collector_log=(B/'numa-context.log').open('a')
 collector=S.Popen(['python3',str(O/'scripts/numa_context.py')],stdout=collector_log,stderr=S.STDOUT)
 try:
  with (B/'campaign.log').open('a') as log:
   S.run(['python3','-u',str(O/'scripts/campaign.py')],stdout=log,stderr=S.STDOUT,check=True)
  state('postprocessing')
  with (B/'finalize.log').open('a') as log:
   S.run(['python3','-u',str(O/'scripts/postprocess.py')],stdout=log,stderr=S.STDOUT,check=True)
  state('complete',github_publication='pending human-readable report review by the assistant')
 except BaseException as e:
  state('failed',error=str(e));raise
 finally:
  release()
  try:collector.wait(timeout=15)
  except S.TimeoutExpired:collector.terminate();collector.wait(timeout=10)
  collector_log.close()
if __name__=='__main__':
 if '--release-only' in sys.argv:release()
 else:main()
