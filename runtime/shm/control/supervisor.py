"""One executable process per preallocated client slot. Never restart a slot."""
import vmweave_env as env
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from kube import API
from observe import report

def main():
    if env.get("VMWEAVE_RESOURCE_BACKEND") is None:
        os.environ["VMWEAVE_RESOURCE_BACKEND"]="hami"
    aid=env.require('VMWEAVE_ALLOCATION')
    if not re.fullmatch('[0-9a-f]{32}',aid):raise ValueError('invalid allocation')
    count=int(env.require('VMWEAVE_SESSIONS'))
    if not 1<=count<=32:raise ValueError('invalid session count')
    processes=[];stopping=False;api=API();worker_reported=False;guest_reported=False
    def stop(*args):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    ready=Path('/tmp/vmweave-worker-ready')
    legacy_ready=Path('/tmp/flyt-worker-ready')
    if legacy_ready.exists():raise RuntimeError('stale legacy readiness marker')
    if legacy_ready.is_symlink():legacy_ready.unlink()
    legacy_ready.symlink_to(ready)
    try:
        for slot in range(count):
            for suffix in ('mapped','guest'):
                p=Path(f'/tmp/vmweave-slot-{slot}-{suffix}')
                if p.exists():raise RuntimeError('stale session markers')
            processes.append(subprocess.Popen([('/opt/vmweave/bin/vmweave-shm-session-worker' if env.get('VMWEAVE_PERSISTENT')=='1' else '/opt/vmweave/bin/vmweave-shm-worker'),'/flyt-channel/'+aid,str(slot)],start_new_session=True))
        while not stopping:
            live=[p.poll() is None for p in processes]
            if not any(live):break
            if all(live) and all(Path(f'/tmp/vmweave-slot-{i}-mapped').exists() for i in range(count)):
                ready.touch(exist_ok=True)
                if not worker_reported:
                    try:report(api,'worker','Mapped');worker_reported=True
                    except Exception:pass
            else:ready.unlink(missing_ok=True)
            if all(live) and all(Path(f'/tmp/vmweave-slot-{i}-guest').exists() for i in range(count)) and not guest_reported:
                try:report(api,'guest','Mapped');guest_reported=True
                except Exception:pass
            # Failed slots stay failed; surviving clients keep their own process.
            time.sleep(.2)
    finally:
        ready.unlink(missing_ok=True)
        legacy_ready.unlink(missing_ok=True)
        for p in processes:
            if p.poll() is None:os.killpg(p.pid,signal.SIGTERM)
        deadline=time.monotonic()+10
        for p in processes:
            try:p.wait(timeout=max(.01,deadline-time.monotonic()))
            except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
        # wait() completed for every isolated child; this process never maps BAR/backing.
        # Retain finalizer if the API is unavailable; do not manufacture evidence.
        try:report(api,'worker','Detached')
        except Exception as e:print('detach evidence not recorded:',type(e).__name__,flush=True)
    return 0 if all(p.returncode==0 for p in processes) else 1
if __name__=='__main__':raise SystemExit(main())
