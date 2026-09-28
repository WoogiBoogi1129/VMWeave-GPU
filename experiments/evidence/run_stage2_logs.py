"""One new Stage 2 run: raw logs and data only; no UI, video or terminal recording."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import time
from campaign_runtime import Run, ROOT, NS, GPU, call, k, get, save, wait
from run_stage1 import clean_object
from verify_stage2 import parse, verify

WORKER='localhost/flyt-worker@sha256:bdac2a998228f13380efb7c80b38c7218ed639b12c00f9cc8d150d83f0c78dae'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--name',required=True);a=p.parse_args()
    base=a.base.resolve();out=a.output.resolve()
    if get('vm',a.name):raise ValueError('A new VM name is required')
    out.mkdir(parents=True,exist_ok=False);raw=out/'raw';raw.mkdir()
    art=base/'artifacts';art.mkdir(parents=True,exist_ok=True)
    for n in ['campaign-probe-guest','campaign-probe-native','libflyt_guest.so','stage2-probe','guest-key','guest-key.pub']:
        shutil.copy2(ROOT/'.local/stage2-20260928/artifacts'/n,art/n)
    before=json.loads(k(['get','vmi','-A','-o','json']))['items']
    baseline=lambda xs:[{k:v['metadata'][k] for k in ['namespace','name','uid']} for v in xs]
    save(raw/'baseline-vmis.json',baseline(before))
    save(out/'protocol.json',{'name':a.name,'scope':'One independent Stage 2 log demonstration; separate from historical three runs',
        'recording':False,'video':False,'worker_image':WORKER,'gpu_uuid':GPU,'compute':50,'memory_mib':4096,'sessions':1,
        'seed':2031,'input_bytes':1048576,'elements':262144,'blocks':1024,'threads':256,'kernel_addend':19,
        'trace_on':True,'timing_experiment':False,'base_commit':call(['git','rev-parse','HEAD']).strip(),
        'binary_sha256':{n:hashlib.sha256((art/n).read_bytes()).hexdigest() for n in ['stage2-probe','libflyt_guest.so']}})
    run=Run(base,a.name,compute=50,worker_image=WORKER,scope='Stage 2 raw logs; no recording');proc=None
    try:
        run.prepare()
        channel=get('flytsharedmemorychannel',a.name+'-channel');status=channel['status']
        save(raw/'trace-binding.json',{'allocation':status['allocation'],'generation':status['generation'],
            'session_id':status['sessions'][0],'gpu_uuid':status['gpuUUID'],'channel_uid':run.uid,
            'worker_uid':status['workerPodUID'],'vmi_uid':run.vmi_uid})
        scp=['scp','-i',str(art/'guest-key'),'-o','BatchMode=yes','-o','UserKnownHostsFile='+str(run.out/'known-hosts')]
        call(scp+[str(art/'stage2-probe'),'ubuntu@'+run.ip+':/tmp/campaign/'])
        command='cd /tmp/campaign && sudo env FLYT_TRACE_REQUESTS=1 FLYT_LAYOUT=/tmp/campaign/layout.bin FLYT_IVSHMEM_BDF='+run.bdf+' FLYT_SLOT=0 LD_LIBRARY_PATH=/tmp/campaign ./stage2-probe 2031'
        save(raw/'command.json',{'guest_ssh_command':run.ssh+[command],'worker_log_command':['kubectl','logs','-n',NS,run.worker],
                                'worker_image':WORKER,'guest_command':command})
        print('Executing in Guest:',command,flush=True)
        with (raw/'stdout.jsonl').open('w') as stdout,(raw/'guest-stderr.txt').open('w') as stderr:
            proc=subprocess.Popen(run.ssh+[command],stdout=stdout,stderr=stderr,text=True)
            # The existing probe holds its allocation for four seconds per stage.
            wait(lambda:'cudaMalloc_1MiB' in (raw/'stdout.jsonl').read_text() or proc.poll() is not None,seconds=120)
            if proc.poll() is not None:raise RuntimeError('Probe ended before observation')
            runtime=json.loads(k(['exec','-i','-n',NS,'evidence-c28-affinity','--','python3','-',status['workerPodUID']],
                                 input=(ROOT/'experiments/evidence/campaign_runtime_info.py').read_text()))
            save(raw/'runtime-libraries.json',runtime)
            save(raw/'applied.json',{key:clean_object(get(kind,name),pod=key=='worker') for key,kind,name in [
                ('request','flytgpurequest',a.name+'-request'),('profile','flytgpuprofile',a.name+'-profile'),
                ('channel','flytsharedmemorychannel',a.name+'-channel'),('worker','pod',run.worker)]})
            (raw/'gpu-processes.csv').write_text(call(['nvidia-smi','-i',GPU,'--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory','--format=csv']))
            code=proc.wait(timeout=120)
        save(raw/'process.json',{'exit_code':code})
        (raw/'worker-stderr.txt').write_text(k(['logs','-n',NS,run.worker]))
        if code:raise RuntimeError('Guest CUDA probe failed')
        hashes={}
        for n in ['input','reference','output']:
            hashes[n]=call(run.ssh+['sha256sum /tmp/campaign/stage2-'+n+'.bin']).split()[0]
        save(raw/'array-hashes.json',hashes)
        call(scp+['ubuntu@'+run.ip+':/tmp/campaign/stage2-output.bin',str(run.out/'output.bin')])
        (raw/'output.bin.gz').write_bytes(gzip.compress((run.out/'output.bin').read_bytes(),mtime=0))
        for role in ['guest','worker']:
            records=parse((raw/(role+'-stderr.txt')).read_text())
            (raw/(role+'-trace.jsonl')).write_text(''.join(json.dumps(row)+'\n' for row in records))
        print((raw/'stdout.jsonl').read_text(),flush=True)
    finally:
        if proc is not None and proc.poll() is None:proc.terminate();proc.wait(timeout=10)
        if not run.uid:
            ch=get('flytsharedmemorychannel',a.name+'-channel')
            if ch and (run.out/'private-prepare'/('FlytSharedMemoryChannel-'+a.name+'-channel.json')).exists():run.uid=ch['metadata']['uid']
        run.close()
        if run.uid:
            wait(lambda:not get('vmi',a.name) and not get('pod',a.name+'-channel-worker'),seconds=180)
            for n in ['identity.json','manifest.json','cpu-pinning.txt','cleanup.json','host-events.jsonl']:
                if (run.out/n).exists():shutil.copy2(run.out/n,raw/n)
            save(raw/'released-channel.json',clean_object(get('flytsharedmemorychannel',a.name+'-channel')))
    result=verify(raw);save(raw/'validation.json',result)
    with (raw/'requests.csv').open('w') as f:
        fields=list(dict.fromkeys(key for row in result['joined'] for key in row))
        writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(result['joined'])
    after=baseline(json.loads(k(['get','vmi','-A','-o','json']))['items'])
    if after!=baseline(before):raise RuntimeError('Baseline VMI set changed')
    save(raw/'final-audit.json',{'baseline_vmis':after,'baseline_preserved':True,'vmi_worker_absent':True,
        'gpu_processes_after':call(['nvidia-smi','-i',GPU,'--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader']).strip()})
    print(json.dumps({k:v for k,v in result.items() if k!='joined'},indent=2),flush=True)

if __name__=='__main__':main()
