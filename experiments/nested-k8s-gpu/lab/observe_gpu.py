#!/usr/bin/env python3
"""Observe a specified lab Channel's CUDA child and host GPU; never launches work."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('context', 'namespace', 'vm', 'gpu_uuid'):
        p.add_argument('--'+key.replace('_', '-'), required=True)
    p.add_argument('--expect', choices=['active', 'idle'], required=True)
    p.add_argument('--timeout', type=int, default=60)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        p.error('output exists; preserve earlier observations')
    def k(*args):
        return subprocess.check_output(['kubectl', '--context', a.context, *args], text=True, timeout=20)
    code = """import os,json
out=[]
for pid in os.listdir('/proc'):
 if not pid.isdigit():continue
 try:
  cmd=open('/proc/'+pid+'/cmdline','rb').read().replace(bytes([0]),b' ').decode()
  if cmd.split(' ')[0].endswith('shm-session-worker') and '--session' in cmd:
   out.append({'pid':int(pid),'command':cmd})
 except (FileNotFoundError,ProcessLookupError):pass
print(json.dumps(out))"""
    started = time.monotonic()
    identity = None
    while True:
        channel = json.loads(k('get', 'sharedmemorychannel', a.vm, '-n', a.namespace, '-o', 'json'))
        s = channel['status']
        assert s['phase'] == 'Ready' and s['gpuUUID'] == a.gpu_uuid
        current = (channel['metadata']['uid'], s['workerPodUID'], s['resourcePrefix'])
        if identity is None:
            identity = current
        assert current == identity, 'runtime changed during observation; inspect old runtime reclamation separately'
        worker = s['resourcePrefix']+'-worker'
        pod = json.loads(k('get', 'pod', worker, '-n', a.namespace, '-o', 'json'))
        assert pod['metadata']['uid'] == s['workerPodUID'], 'Channel/Worker UID mismatch'
        children = json.loads(k('exec', '-n', a.namespace, worker, '--', 'python3', '-c', code))
        apps = subprocess.check_output(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid,used_memory',
                                        '--format=csv,noheader,nounits'], text=True, timeout=20)
        matched = []
        for line in apps.splitlines():
            cols = [x.strip() for x in line.split(',')]
            if len(cols) != 3:
                continue
            pid = int(cols[1])
            try:
                cg = Path(f'/proc/{pid}/cgroup').read_text()
                if s['workerPodUID'] not in cg and s['workerPodUID'].replace('-', '_') not in cg:
                    continue
                status = Path(f'/proc/{pid}/status').read_text()
            except FileNotFoundError:
                continue
            ids = [int(x) for x in next(x for x in status.splitlines() if x.startswith('NSpid:')).split()[1:]]
            assert cols[0] == a.gpu_uuid, 'unexpected physical GPU'
            matched.append({'gpu_uuid': cols[0], 'host_pid': pid, 'namespace_pids': ids, 'cgroup': cg,
                            'memory_mib': cols[2], 'child_matches': any(c['pid'] == ids[-1] for c in children)})
        ok = (not children and not matched) if a.expect == 'idle' else (len(children) == 1 and len(matched) == 1 and matched[0]['child_matches'])
        elapsed = time.monotonic()-started
        result = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'expect': a.expect,
                  'result': 'PASS' if ok and elapsed <= a.timeout else 'FAIL', 'elapsed_seconds': elapsed,
                  'channel_uid': channel['metadata']['uid'], 'channel_status': s,
                  'children': children, 'host_gpu_processes': matched}
        if ok or elapsed >= a.timeout:
            a.output.parent.mkdir(parents=True, exist_ok=True)
            a.output.write_text(json.dumps(result, indent=2)+'\n')
            print(json.dumps(result, indent=2))
            if result['result'] != 'PASS':
                raise SystemExit(1)
            return
        time.sleep(1)


if __name__ == '__main__':
    main()
