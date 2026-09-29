"""Read-only monotonic-to-host clock samples for each active guest.

Fresh guest wall clocks can be stepped by time synchronization. Three SSH probes
map its monotonic clock directly to host UTC, with half-RTT uncertainty. This
independent collector does not alter guest clocks or the frozen workload.
"""
import argparse
import json
import subprocess
import time
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);a=p.parse_args()
base=a.base.resolve()
while not (base/'CLOCK_COLLECTION_COMPLETE').exists():
    for directory in sorted((base/'runs').glob('*')):
        if (directory/'cleanup.json').exists() or (directory/'monotonic-clock-map.json').exists():
            continue
        if not (directory/'stdout.jsonl').exists() or 'MEASUREMENT_START' not in (directory/'stdout.jsonl').read_text():
            continue
        manifest=json.loads((directory/'manifest.json').read_text())
        if manifest['backend']!='shm':
            continue
        try:
            vmi=json.loads(subprocess.check_output(['kubectl','get','vmi',directory.name,'-n','flyt-evidence','-o','json'],text=True,timeout=10))
            ip=vmi['status']['interfaces'][0]['ipAddress']
            cmd=['ssh','-i',str(base/'artifacts/guest-key'),'-o','BatchMode=yes','-o','ConnectTimeout=3',
                 '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(directory/'known-hosts'),
                 'ubuntu@'+ip,"python3 -c 'import time,json; print(json.dumps(dict(guest_utc=time.time(), guest_monotonic=time.monotonic())))'"]
            samples=[]
            for _ in range(3):
                before=time.time()
                value=json.loads(subprocess.check_output(cmd,text=True,timeout=10))
                after=time.time()
                samples.append({**value,'host_before':before,'host_after':after,
                                'host_minus_guest_monotonic':(before+after)/2-value['guest_monotonic'],
                                'uncertainty':(after-before)/2})
            (directory/'monotonic-clock-map.json').write_text(json.dumps(samples,indent=2)+'\n')
            print(json.dumps({'run_id':directory.name,'event':'MONOTONIC_CLOCK_MAPPED','samples':samples}),flush=True)
        except (subprocess.SubprocessError,KeyError,ValueError) as error:
            print(json.dumps({'run_id':directory.name,'error':str(error)}),flush=True)
    time.sleep(1)
