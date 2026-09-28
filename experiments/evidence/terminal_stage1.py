"""Preparation/observation helpers for a real bash/asciinema Stage 1 demonstration.
No web UI. Commands and raw Kubernetes/SSH/NVIDIA output are recorded separately.
"""
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import time
from campaign_runtime import ROOT, NS, GPU, call, k, get, save, wait
from run_stage1 import clean_object, validate

BASE=Path(os.environ['DEMO']).resolve()
OUT=Path(os.environ['RAW']).resolve()
NAME=os.environ['VM']

def connection():
    return json.loads((BASE/'connection.json').read_text())

def ssh():return ['ssh','-F',str(BASE/'ssh-config'),'stage1-vm']

def connect():
    channel=get('flytsharedmemorychannel',NAME+'-channel');status=channel['status']
    vmi=get('vmi',NAME);ip=vmi['status']['interfaces'][0]['ipAddress']
    config=f'Host stage1-vm\n HostName {ip}\n User ubuntu\n IdentityFile {BASE}/artifacts/guest-key\n BatchMode yes\n ConnectTimeout 5\n StrictHostKeyChecking accept-new\n UserKnownHostsFile {BASE}/known-hosts\n'
    (BASE/'ssh-config').write_text(config)
    import subprocess
    wait(lambda:subprocess.run(ssh()+['true'],capture_output=True,timeout=8).returncode==0)
    wait(lambda:get('pod',NAME+'-channel-worker').get('status',{}).get('phase')=='Running')
    channel=get('flytsharedmemorychannel',NAME+'-channel');status=channel['status']
    save(BASE/'channel.json',channel)
    bdf=call(ssh()+["python3 -c \"from pathlib import Path; print(next(p.name for p in Path('/sys/bus/pci/devices').iterdir() if (p/'vendor').read_text().strip()=='0x1af4' and (p/'device').read_text().strip()=='0x1110'))\""]).strip()
    call([sys.executable,ROOT/'scripts/export-shm-guest.py','--channel-json',BASE/'channel.json','--bdf',bdf,'--slot','0','--output',BASE/'guest-config'])
    launcher=next(p for p in json.loads(k(['get','pods','-n',NS,'-o','json']))['items'] if p['metadata']['name'].startswith('virt-launcher-'+NAME+'-'))
    state={'channel_uid':channel['metadata']['uid'],'worker_uid':status['workerPodUID'],'launcher_uid':launcher['metadata']['uid'],
           'allocation':status['allocation'],'worker':NAME+'-channel-worker','launcher':launcher['metadata']['name'],
           'vmi_uid':vmi['metadata']['uid'],'gpu_uuid':status['gpuUUID'],'bdf':bdf}
    save(BASE/'connection.json',state);save(OUT/'identity.json',state)
    probe='''#!/bin/bash
set -euo pipefail
hostname
date -u +%FT%TZ
cd /tmp/campaign
sudo env FLYT_LAYOUT=/tmp/campaign/layout.bin \\
  FLYT_IVSHMEM_BDF=BDF FLYT_SLOT=0 LD_LIBRARY_PATH=/tmp/campaign \\
  ./campaign-probe-guest integer resident 45 0 64 2030 0 - -
'''.replace('BDF FLYT_SLOT',bdf+' FLYT_SLOT')
    (BASE/'run-probe.sh').write_text(probe);shutil.copy2(BASE/'run-probe.sh',OUT/'run-probe.sh')
    call(ssh()+['mkdir -p /tmp/campaign'])
    call(['scp','-F',BASE/'ssh-config',BASE/'run-probe.sh',BASE/'artifacts/campaign-probe-guest',BASE/'artifacts/libflyt_guest.so',BASE/'guest-config/layout.bin','stage1-vm:/tmp/campaign/'])
    pin=(ROOT/'experiments/evidence/campaign_affinity.py').read_text()
    text=k(['exec','-i','-n',NS,'evidence-c28-affinity','--','python3','-',state['launcher_uid'],'0-7'],input=pin)
    text+=k(['exec','-i','-n',NS,'evidence-c28-affinity','--','python3','-',state['worker_uid'],'16-19'],input=pin)
    (OUT/'cpu-pinning.txt').write_text(text)
    print('SSH connection and probe files prepared for',NAME)
    print('Guest CPU: 0-7; Worker CPU: 16-19; Guest BAR:',bdf)

def observe():
    state=connection();channel=get('flytsharedmemorychannel',NAME+'-channel')
    wait(lambda:get('flytsharedmemorychannel',NAME+'-channel')['status']['phase']=='Ready',seconds=90)
    def helper(filename,args):
        return json.loads(k(['exec','-i','-n',NS,'evidence-c28-affinity','--','python3','-',*args],input=(ROOT/'experiments/evidence'/filename).read_text()))
    mapping=helper('stage1_host_mapping.py',[state['worker_uid'],state['launcher_uid'],state['allocation']])
    runtime=helper('campaign_runtime_info.py',[state['worker_uid']])
    raw_gpu=call(['nvidia-smi','-i',GPU,'--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory','--format=csv,noheader,nounits'])
    (OUT/'gpu-processes.csv').write_text(raw_gpu)
    gpu=[]
    for line in raw_gpu.splitlines():
        uuid,pid,process,memory=[x.strip() for x in line.split(',')]
        gpu.append({'gpu_uuid':uuid,'pid':int(pid),'process':process,'memory_mib':memory})
    vmi=get('vmi',NAME)
    snapshot={key:clean_object(get(kind,name),pod=key=='worker') for key,kind,name in [
        ('request','flytgpurequest',NAME+'-request'),('profile','flytgpuprofile',NAME+'-profile'),
        ('channel','flytsharedmemorychannel',NAME+'-channel'),('worker','pod',state['worker'])]}
    snapshot['vmi']={'metadata':{key:vmi['metadata'][key] for key in ['name','uid','ownerReferences']},'status':vmi['status']}
    snapshot['attachments']=[clean_object(x) for x in json.loads(k(['get','flytchannelattachments','-n',NS,'-o','json']))['items'] if x['spec']['channelRef']['uid']==state['channel_uid']]
    snapshot['gpu_processes']=gpu;snapshot['observed_utc']=time.time()
    code='''import json
from pathlib import Path
p=Path('/sys/bus/pci/devices')/BDF
parts=(p/'resource').read_text().splitlines()[2].split();rows=[]
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:
  if b'/tmp/campaign/campaign-probe-guest' not in (proc/'cmdline').read_bytes() and b'./campaign-probe-guest' not in (proc/'cmdline').read_bytes():continue
  rows += [line for line in (proc/'maps').read_text().splitlines() if BDF in line and 'resource2' in line]
 except (FileNotFoundError,ProcessLookupError):pass
print(json.dumps({'bdf':BDF,'bar2_bytes':int(parts[1],16)-int(parts[0],16)+1,'probe_bar_maps':rows}))
'''
    guest=json.loads(call(ssh()+['sudo python3 -c '+shlex.quote('BDF='+repr(state['bdf'])+'\n'+code)]))
    for name,data in [('applied.json',snapshot),('host-mapping.json',mapping),('runtime-libraries.json',runtime),('guest-bar.json',guest)]:save(OUT/name,data)
    checks=validate(snapshot,mapping,runtime,guest);save(OUT/'checks.json',checks)
    if not all(checks.values()):raise RuntimeError('Stage 1 observation failed: '+str(checks))
    print('Saved raw observations: applied.json, host-mapping.json, runtime-libraries.json, guest-bar.json')

def cleanup():
    ch=get('flytsharedmemorychannel',NAME+'-channel')
    if not ch:return
    # This helper owns only the resources created by the explicit prepare command.
    expected=json.loads((BASE/'private-prepare'/('FlytSharedMemoryChannel-'+NAME+'-channel.json')).read_text())
    if ch['spec']['vmRef']!=expected['spec']['vmRef'] or ch['spec']['requestRef']!=expected['spec']['requestRef']:
        raise RuntimeError('Ownership mismatch')
    uid=ch['metadata']['uid']
    print(k(['patch','flytsharedmemorychannel',NAME+'-channel','-n',NS,'--type=json','-p',json.dumps([
        {'op':'test','path':'/metadata/uid','value':uid},{'op':'add','path':'/spec/drain','value':True}])]).strip())
    wait(lambda:get('flytsharedmemorychannel',NAME+'-channel')['status']['phase']=='Released')
    wait(lambda:not get('vmi',NAME) and not get('pod',NAME+'-channel-worker'),seconds=180)
    save(OUT/'released-channel.json',clean_object(get('flytsharedmemorychannel',NAME+'-channel')))
    save(OUT/'cleanup.json',{'channel_uid':uid,'released':True,'vmi_absent':True,'worker_absent':True,'observed_utc':time.time()})

if __name__=='__main__':
    {'connect':connect,'observe':observe,'cleanup':cleanup}[sys.argv[1]]()
