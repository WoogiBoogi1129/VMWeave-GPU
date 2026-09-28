"""Drive real bash commands in a PTY recorded by unmodified asciinema 2.4.0.

The automation enters commands; it does not fabricate terminal output or claim
human authorship. No bespoke result viewer. Capture markers are shell comments.
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time
import pexpect
from campaign_runtime import ROOT, NS, GPU, GUEST, save, k, get

BASE=ROOT/'.local/stage1-terminal-20260928'
PUBLIC=ROOT/'experiments/evidence/results/2026-09-28-stage1-terminal'
NAME='evidence-s1-terminal-0928b'

def main():
    if get('vm',NAME):raise RuntimeError('Experiment name already exists')
    PUBLIC.mkdir(parents=True,exist_ok=False);raw=PUBLIC/'raw';raw.mkdir()
    (BASE/'artifacts').mkdir(exist_ok=True)
    for name in ['campaign-probe-guest','campaign-probe-native','libflyt_guest.so','guest-key','guest-key.pub']:
        shutil.copy2(ROOT/'.local/stage1-20260928/artifacts'/name,BASE/'artifacts'/name)
    assert os.access(BASE/'artifacts/campaign-probe-guest',os.X_OK)
    images=json.loads((ROOT/'.local/evidence-20260924/images.json').read_text())
    values={'DEMO':str(BASE),'RAW':str(raw),'VM':NAME,'NS':NS,'GPU':GPU,'GUEST_IMAGE':GUEST,
            'CONTROL_IMAGE':images['control'],'WORKER_IMAGE':images['worker'],'HOOK_IMAGE':images['hook']}
    (BASE/'config.env').write_text(''.join('export '+key+'='+shlex.quote(value)+'\n' for key,value in values.items()))
    prepare='''#!/bin/bash
set -euo pipefail
python3 scripts/prepare-evidence-vm.py --name "$VM" \\
  --reuse-pvc evidence-vm-a-backing --public-key "$DEMO/artifacts/guest-key.pub" \\
  --memory-mib 4096 --compute 50 --sessions 1 \\
  --guest-image "$GUEST_IMAGE" --worker-image "$WORKER_IMAGE" \\
  --control-image "$CONTROL_IMAGE" --hook-image "$HOOK_IMAGE" \\
  --output "$DEMO/private-prepare"
'''
    (BASE/'prepare.sh').write_text(prepare);(raw/'prepare.sh').write_text(prepare)
    rc='''PS1='\\u@\\h:\\W\\$ '
PROMPT_COMMAND='printf "%s\\n" "$?" > "$DEMO/last-exit"'
HISTFILE=/dev/null
set -o pipefail
'''
    (BASE/'bashrc').write_text(rc)
    before=json.loads(k(['get','vmi','-A','-o','json']))['items']
    baseline=[{'namespace':x['metadata']['namespace'],'name':x['metadata']['name'],'uid':x['metadata']['uid'],'phase':x['status']['phase']} for x in before]
    save(raw/'baseline-vmis.json',baseline)
    save(PUBLIC/'protocol.json',{'scope':'One new Stage 1 demonstration, separate from historical 3 repeats',
        'recording':'Real bash PTY using asciinema 2.4.0; agent-entered commands; output is not reconstructed',
        'player':'Official asciinema-player 3.6.3, default terminal rendering',
        'name':NAME,'memory_mib':4096,'compute':50,'sessions':1,'probe':'integer resident 45 seconds; warmup 10 seconds; seed 2030',
        'gpu_uuid':GPU,'images':{**images,'guest':GUEST},'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'binary_sha256':{n:hashlib.sha256((BASE/'artifacts'/n).read_bytes()).hexdigest() for n in ['campaign-probe-guest','libflyt_guest.so']}})
    env=os.environ.copy();env.update(values,TERM='xterm-256color',SHELL='/bin/bash',ASCIINEMA_CONFIG_HOME=str(BASE/'asciinema-config'))
    command='bash --noprofile --rcfile '+shlex.quote(str(BASE/'bashrc'))+' -i'
    child=pexpect.spawn(str(BASE/'venv/bin/asciinema'),['rec','-q','--cols','132','--rows','34','-c',command,str(PUBLIC/'stage1.cast')],
                        cwd=str(ROOT),env=env,encoding='utf-8',timeout=600,dimensions=(34,132))
    # Hostname and working directory are expanded by bash, not painted by a UI.
    prompt=r'ubuntu@gpu-4:flyt-k8s-poc-github\$ '
    commands=[];markers=[]
    def cmd(command,timeout=600):
        child.sendline(command);child.expect(prompt,timeout=timeout)
        status=int((BASE/'last-exit').read_text())
        commands.append({'command':command,'exit_code':status,'completed_utc':time.time()})
        save(PUBLIC/'commands.json',commands)
        if status:raise RuntimeError('Command failed: '+command)
    def begin(title):cmd('clear');cmd('# '+title)
    def frame(key):
        cmd('# CAPTURE '+key);markers.append(key);time.sleep(3)
    try:
        child.expect(prompt)
        begin('0. BEFORE THE REQUEST: no experiment VM or GPU process')
        cmd('date -u +%FT%TZ')
        cmd('kubectl get vmi "$VM" -n "$NS" --ignore-not-found')
        cmd('nvidia-smi -i 1 --query-gpu=index,name --format=csv')
        cmd('nvidia-smi -i 1 --query-compute-apps=pid,process_name --format=csv')
        frame('00-before')
        begin('1. REGISTER GPU REQUEST: 4096 MiB / compute 50 / one session')
        cmd('cat "$DEMO/prepare.sh"')
        cmd('bash "$DEMO/prepare.sh" | tee "$RAW/create.log"')
        cmd('kubectl get flytgpurequest "$VM-request" -n "$NS" -o json | jq ".spec | {count,memory,compute}" | tee "$RAW/request-values.json"')
        frame('01-request')
        begin('2. START THE VM AND WAIT FOR ITS WORKER')
        cmd('kubectl wait -n "$NS" "flytsharedmemorychannel/$VM-channel" --for=jsonpath=\'{.status.phase}\'=BackingReady --timeout=180s')
        cmd('kubectl patch vm "$VM" -n "$NS" --type=merge -p \'{"spec":{"runStrategy":"Always"}}\'')
        cmd('kubectl wait -n "$NS" "vmi/$VM" --for=jsonpath=\'{.status.phase}\'=Running --timeout=300s')
        cmd('python3 experiments/evidence/terminal_stage1.py connect')
        cmd('kubectl get vmi "$VM" -n "$NS" -o wide | tee "$RAW/vmi.txt"')
        cmd('kubectl get pod "$VM-channel-worker" -n "$NS" -o wide | tee "$RAW/worker.txt"')
        frame('02-vm-worker')
        begin('3. COMPARE REQUESTED VALUES WITH ACTUAL WORKER LIMITS')
        cmd('kubectl get flytgpurequest "$VM-request" -n "$NS" -o json | jq ".spec | {count,memory,compute}"')
        cmd('kubectl get pod "$VM-channel-worker" -n "$NS" -o json | jq ".spec.containers[0].resources.limits" | tee "$RAW/worker-limits.json"')
        cmd('# This checks configuration delivery, not utilization or quota enforcement.')
        frame('03-settings')
        begin('4. EXECUTE THE CUDA PROGRAM INSIDE THE VM')
        cmd('cat "$DEMO/run-probe.sh"')
        cmd('ssh -n -F "$DEMO/ssh-config" stage1-vm "bash /tmp/campaign/run-probe.sh" > "$RAW/guest-stdout.log" 2> "$RAW/guest-stderr.log" &')
        cmd('PROBE_JOB=$!')
        cmd('sleep 3')
        cmd('head -n 3 "$RAW/guest-stdout.log"')
        frame('04-guest-command')
        begin('5. MATCH THE WORKER HOST PID TO THE GPU PROCESS PID')
        cmd('python3 experiments/evidence/terminal_stage1.py observe')
        cmd('jq -r \'.[] | select(.role=="worker") | "Worker host PID: \\(.pid)\\nWorker Pod UID: \\(.pod_uid)"\' "$RAW/host-mapping.json"')
        cmd('nvidia-smi -i 1 --query-compute-apps=pid,process_name --format=csv | tee "$RAW/gpu-live.txt"')
        cmd('kubectl get flytsharedmemorychannel "$VM-channel" -n "$NS" -o custom-columns=NAME:.metadata.name,PHASE:.status.phase | tee "$RAW/channel-ready.txt"')
        frame('05-gpu-pid')
        begin('6. WAIT FOR COMPLETION AND CHECK THE CALCULATION RESULT')
        cmd('wait "$PROBE_JOB"')
        cmd('tail -n 1 "$RAW/guest-stdout.log" | tee "$RAW/result.json" | jq "{status,checked_elements,mismatches}"')
        cmd('jq -e \'.status=="PASS" and .checked_elements==524288 and .mismatches==0\' "$RAW/result.json"')
        frame('06-result')
        begin('7. DRAIN THIS EXPERIMENT AND CHECK RELEASE')
        cmd('python3 experiments/evidence/terminal_stage1.py cleanup')
        cmd('kubectl get flytsharedmemorychannel "$VM-channel" -n "$NS" -o custom-columns=NAME:.metadata.name,PHASE:.status.phase')
        cmd('kubectl get vmi "$VM" -n "$NS" --ignore-not-found')
        cmd('kubectl get pod "$VM-channel-worker" -n "$NS" --ignore-not-found')
        cmd('nvidia-smi -i 1 --query-compute-apps=pid,process_name --format=csv')
        frame('07-released')
        child.sendline('exit');child.expect(pexpect.EOF);child.close()
        if child.exitstatus!=0:raise RuntimeError('Recorder exit failure')
        after=json.loads(k(['get','vmi','-A','-o','json']))['items']
        observed=[{'namespace':x['metadata']['namespace'],'name':x['metadata']['name'],'uid':x['metadata']['uid'],'phase':x['status']['phase']} for x in after]
        save(raw/'final-vmis.json',observed)
        if observed!=baseline:raise RuntimeError('Baseline VM set changed')
        # Capture times come from the recorder's own output event times.
        events=[json.loads(line) for line in (PUBLIC/'stage1.cast').read_text().splitlines()]
        chapters=[]
        for marker in markers:
            stamp=next(row[0] for row in events[1:] if row[1]=='o' and '# CAPTURE '+marker in row[2])
            chapters.append({'name':marker,'seconds':stamp+1})
        save(PUBLIC/'chapters.json',chapters)
        save(PUBLIC/'validation.json',{'status':'PASS','stage1_checks':json.loads((raw/'checks.json').read_text()),
             'result':json.loads((raw/'result.json').read_text()),'baseline_vmis_preserved':True,
             'cleanup':json.loads((raw/'cleanup.json').read_text()),'terminal_commands':len(commands),
             'all_recorded_commands_exit_zero':all(x['exit_code']==0 for x in commands)})
    finally:
        if child.isalive():child.close(force=True)
        if (BASE/'private-prepare'/('FlytSharedMemoryChannel-'+NAME+'-channel.json')).exists():
            ch=get('flytsharedmemorychannel',NAME+'-channel')
            if ch and ch.get('status',{}).get('phase')!='Released':
                subprocess.run([sys.executable,'experiments/evidence/terminal_stage1.py','cleanup'],cwd=ROOT,env=env,check=True)

if __name__=='__main__':main()
