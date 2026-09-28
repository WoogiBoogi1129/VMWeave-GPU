"""Offline checks for the terminal demonstration and its raw Stage 1 observations."""
import argparse
import json
from pathlib import Path
from run_stage1 import validate

def verify(root):
    root=Path(root);raw=root/'raw'
    read=lambda p:json.loads(p.read_text())
    checks=validate(*[read(raw/name) for name in ['applied.json','host-mapping.json','runtime-libraries.json','guest-bar.json']])
    if not all(checks.values()):raise ValueError('Stage 1 observation mismatch')
    result=read(raw/'result.json')
    if result['status']!='PASS' or result['checked_elements']!=524288 or result['mismatches']!=0:
        raise ValueError('Incorrect calculation')
    if result['seed']!=2030:raise ValueError('Wrong demonstration seed')
    commands=read(root/'commands.json')
    if not commands or any(c['exit_code'] for c in commands):raise ValueError('A command failed')
    if not any(c['command']=='wait "$PROBE_JOB"' for c in commands):raise ValueError('No process exit observation')
    events=[json.loads(line) for line in (root/'stage1.cast').read_text().splitlines()]
    if events[0]['version']!=2 or events[0]['width']!=132 or events[0]['height']!=34:raise ValueError('Unexpected recorder format')
    text=''.join(e[2] for e in events[1:] if e[1]=='o')
    chapters=read(root/'chapters.json')
    if len(chapters)!=8:raise ValueError('Missing stage')
    for c in chapters:
        if '# CAPTURE '+c['name'] not in text:raise ValueError('Capture marker absent from original recording')
        if not 0<c['seconds']<events[-1][0]:raise ValueError('Invalid capture time')
    if any(a[0]>b[0] for a,b in zip(events[1:],events[2:])):raise ValueError('Recording time reversed')
    pids=[row['pid'] for row in read(raw/'host-mapping.json') if row['role']=='worker']
    if len(pids)!=1 or f'Worker host PID: {pids[0]}' not in text:raise ValueError('Worker identity not shown')
    gpu=(raw/'gpu-live.txt').read_text()
    if str(pids[0]) not in gpu or '/opt/flyt/bin/flyt-shm-worker' not in gpu:raise ValueError('GPU PID mismatch')
    cleanup=read(raw/'cleanup.json')
    if not all(cleanup[k] for k in ['released','vmi_absent','worker_absent']):raise ValueError('Cleanup incomplete')
    if read(raw/'released-channel.json')['status']['phase']!='Released':raise ValueError('Channel not released')
    if read(raw/'baseline-vmis.json')!=read(raw/'final-vmis.json'):raise ValueError('Baseline VM changed')
    return {'status':'PASS','stage1_checks':len(checks),'checked_elements':524288,'mismatches':0,
            'recorded_commands':len(commands),'chapters':len(chapters),'worker_host_pid':pids[0],
            'recording_seconds':events[-1][0],'cleanup':'Released; VMI/Worker absent','baseline_preserved':True}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args()
    print(json.dumps(verify(a.root),indent=2))
