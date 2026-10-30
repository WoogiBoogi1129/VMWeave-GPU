"""Bounded transfer/Rodinia run on the retained cluster; fixed historical paths.

Reuses read-only inventory/observation helpers from the preserved SGEMM runner.
Prepare once, then run once. Never reuses existing measurements or changes operators.
"""
import argparse
import hashlib
import importlib.util
import json
import re
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path

EXP=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('sgemm_helpers',EXP/'throughput/run.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
h.OUT=EXP/'results/20261030-transfer-app-throughput'
SRC=EXP/'transfer-app'
REMOTE='/home/ubuntu/nested/transfer-app-20261030'
OLD=h.ROOT/'experiments/ai-passthrough/results/20261026-rodinia-steady'
TAG='localhost/nested-transfer-app:20261030'
CASES={'copy':[],'nw':['2048','10'],'srad':['2048','2048','0','127','0','127','0.5','2']}

def connect():
    for role,name in [('cp','vw-k8s-cp-01'),('worker',h.VM)]:
        h.IPS[role]=h.obj('get','svc',name,'-n',h.NS)['spec']['clusterIP']

def upload(path,name):
    subprocess.run(h.sshargs('worker','cat > '+shlex.quote(REMOTE+'/'+name)),input=path.read_bytes(),check=True,timeout=60)

def preflight(label):
    c=h.snapshot(label)
    assert c['status']['phase']=='Ready' and c['status']['gpuUUID']==h.GPU
    nodes=h.iobj('get','nodes')['items']
    assert len(nodes)==2 and all(any(x['type']=='Ready' and x['status']=='True' for x in n['status']['conditions']) for n in nodes)
    assert not any(j.get('status',{}).get('active',0) for j in h.iobj('get','jobs','-n',h.INNER)['items'])
    h.observe('idle',label)
    assert h.GPU not in h.call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader'])
    return c

def prepare(uploaded=False):
    if (h.OUT/'prepared.json').exists():raise RuntimeError('already prepared')
    if (h.OUT/'started.json').exists():raise RuntimeError('measurements already started')
    preflight('before-build-resume' if uploaded else 'before-preparation')
    if not uploaded:h.ssh('worker','test ! -e '+REMOTE+' && mkdir -m 755 '+REMOTE)
    for name in ('copy.c','barrier.c','Containerfile'):upload(SRC/name,name)
    expected=json.loads((OLD/'manifest.json').read_text())['binaries']
    refs={}
    for name in ('nw','srad'):
        p=h.ROOT/'.local/rodinia-steady-20261026'/name
        assert hashlib.sha256(p.read_bytes()).hexdigest()==expected[name]
        upload(p,name)
        refs[name]=json.loads((OLD/'qualification/native'/name/'result.json').read_text())
    h.save('reference/native-outputs.json',refs)
    h.save('reference/rodinia-binary-hashes.json',{n:expected[n] for n in ('nw','srad')})
    runtime=h.ROOT/'.local/thesis-isolation-20261012/bundle-stage/opt/flyt-cuda-libs/libcudart.so.12'
    upload(runtime,'libcudart.so.12')
    build=' && '.join([
        'cd '+REMOTE,
        'cp /opt/vmweave/lib/libvmweave_guest.so .',
        'cp -L /usr/lib/x86_64-linux-gnu/libstdc++.so.6 /lib/x86_64-linux-gnu/libgcc_s.so.1 .',
        'chmod 755 nw srad',
        'gcc -std=c11 -O2 -Wall -Wextra -Werror copy.c -L. -lvmweave_guest -o copy',
        'gcc -std=c11 -O2 -Wall -Wextra -Werror -shared -fPIC barrier.c -ldl -o barrier.so',
        'sudo podman build --pull=false --network=none -t '+TAG+' -f Containerfile .'])
    try:h.save('build.log',h.ssh('worker',build,stderr=subprocess.STDOUT,timeout=180))
    except subprocess.CalledProcessError as e:
        h.save('build-failure.log',e.output);raise
    metadata=json.loads(h.ssh('worker','sudo podman image inspect '+TAG))[0]
    h.save('inventory/image.json',metadata);image=metadata['RepoDigests'][0]
    names=['copy','nw','srad','barrier.so','libvmweave_guest.so','libcudart.so.12','libstdc++.so.6','libgcc_s.so.1']
    host=h.ssh('worker','cd '+REMOTE+' && sha256sum '+shlex.join(names))
    paths=['/opt/bench/'+('bin/' if n in ('copy','nw','srad') else 'lib/')+n for n in names]
    container=h.ssh('worker','sudo podman run --rm --network=none --entrypoint /usr/bin/sha256sum '+shlex.quote(image)+' '+shlex.join(paths))
    assert [s.split()[0] for s in host.splitlines()]==[s.split()[0] for s in container.splitlines()]
    h.save('inventory/binary-library.sha256',host+container)
    h.save('inventory/guest-environment.txt',h.ssh('worker','uname -a; ldd --version | head -1; getent group vmweave; sudo systemctl is-active vmweave-guest-broker kubelet crio; sha256sum /opt/vmweave/lib/libvmweave_guest.so; cat /opt/vmweave/source-revision.txt'))
    h.save('inventory/gpu.csv',h.call(['nvidia-smi','-i',h.GPU,'--query-gpu=uuid,name,driver_version','--format=csv']))
    h.save('prepared.json',{'at':h.utc(),'image':image,'source_git':h.call(['git','rev-parse','HEAD']).strip()})
    print('Prepared '+image,flush=True)

def command(work,mode,name):
    base=REMOTE if mode=='guest' else '/opt/bench'
    bindir=base if mode=='guest' else base+'/bin'
    libdir=base if mode=='guest' else base+'/lib'
    workdir='/tmp/'+name
    barrier=workdir+'/go'
    env=['VMWEAVE_BROKER_SOCKET=/run/vmweave/gpu.sock','LD_LIBRARY_PATH='+libdir]
    args=[bindir+'/'+work]
    if work=='copy':args.append(barrier)
    else:
        env+=['LD_PRELOAD='+libdir+'/barrier.so:'+libdir+'/libvmweave_guest.so',
              'VMWEAVE_MIRROR_DEVICE_VA=1','VMWEAVE_TRACE_REQUESTS=0',
              'EXPERIMENT_BARRIER='+barrier,'EXPERIMENT_REPEATS=2']
        args+=CASES[work]
    cmd='set -eu; mkdir '+shlex.quote(workdir)+'; cd '+shlex.quote(workdir)+'; '+shlex.join(['timeout','-k','5','240','env',*env,*args])
    if work!='copy':cmd+='; sha256sum output-*.bin'
    return cmd,barrier

def job(name,cmd,image):
    j=h.job(name,1024,image,998)
    j['metadata']['labels']={'experiment':'transfer-app-20261030'}
    j['spec']['activeDeadlineSeconds']=300
    c=j['spec']['template']['spec']['containers'][0]
    c.update({'name':'benchmark','command':['/bin/sh','-c'],'args':[cmd],'env':[],
              'resources':{'requests':{'cpu':'100m','memory':'256Mi'},'limits':{'memory':'1Gi'}}})
    return j

def check(work,log):
    if work=='copy':
        rows=h.records(log)
        assert any(x['event']=='PASS' for x in rows)
        cells=[x for x in rows if x['event']=='copy_result']
        assert len(cells)==8
        for r in cells:
            assert r['correct'] and r['count']>=20 and r['seconds']>=2
            assert len(r['completion_seconds'])==len(r['api_return_seconds'])==r['count']
            assert all(0<a<=b for a,b in zip(r['api_return_seconds'],r['completion_seconds']))
        return {'records':rows}
    rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith('EXPERIMENT_SAMPLE ')]
    assert len(rows)==4 and [r['warmup'] for r in rows]==[True,True,False,False]
    assert all(r['seconds']>0 for r in rows)
    hashes=dict((name,digest) for digest,name in re.findall(r'^([0-9a-f]{64})  (output-\d+.bin)$',log,re.M))
    ref=json.loads((h.OUT/'reference/native-outputs.json').read_text())[work]['hashes']['output-02.bin']
    assert len(hashes)==4 and set(hashes.values())=={ref},'full output reference mismatch'
    return {'samples':rows,'output_hashes':hashes,'correct':True}

def execute(work,mode,pair,image):
    name=f'xferapp30-{work}-{pair}-{mode}'
    path=h.OUT/'runs'/name
    assert not path.with_suffix('.log').exists()
    path.parent.mkdir(parents=True,exist_ok=True)
    h.observe('idle',name+'-before')
    cmd,barrier=command(work,mode,name)
    process=None;created=False;pod=None;logfile=None
    try:
        if mode=='guest':
            logfile=path.with_suffix('.log').open('x')
            process=subprocess.Popen(h.sshargs('worker','sg vmweave -c '+shlex.quote(cmd)),stdout=logfile,stderr=subprocess.STDOUT,text=True)
        else:
            manifest=job(name,cmd,image);h.save('manifests/'+name+'.json',manifest)
            h.inner('create','-f','-',input=json.dumps(manifest));created=True
        deadline=time.monotonic()+100
        while True:
            if mode=='guest':
                log=path.with_suffix('.log').read_text()
                if process.poll() is not None:raise RuntimeError(name+' ended before barrier: '+log[-1000:])
            else:
                pods=h.iobj('get','pods','-n',h.INNER,'-l','job-name='+name)['items']
                if pods and pods[0]['status']['phase'] in ('Running','Succeeded','Failed'):
                    pod=pods[0];log=h.inner('logs',pod['metadata']['name'],'-n',h.INNER)
                    path.with_suffix('.log').write_text(log)
                    if pod['status']['phase'] in ('Succeeded','Failed'):raise RuntimeError(name+' ended before barrier: '+log[-1000:])
                else:log=''
            if any(r['event']=='ready' for r in h.records(log)):break
            if time.monotonic()>deadline:raise TimeoutError(name+' ready')
            time.sleep(.5)
        h.observe('active',name+'-active');release=h.utc()
        if mode=='guest':
            h.ssh('worker','touch '+shlex.quote(barrier));rc=process.wait(timeout=250)
            logfile.close();assert rc==0,(name,rc)
        else:
            h.save('runs/'+name+'-pod-start.json',pod)
            h.inner('exec',pod['metadata']['name'],'-n',h.INNER,'--','touch',barrier)
            try:h.inner('wait','-n',h.INNER,'job/'+name,'--for=condition=Complete','--timeout=250s',timeout=270)
            finally:
                path.with_suffix('.log').write_text(h.inner('logs',pod['metadata']['name'],'-n',h.INNER))
                h.save('runs/'+name+'-pod-final.json',h.iobj('get','pod',pod['metadata']['name'],'-n',h.INNER))
        data=check(work,path.with_suffix('.log').read_text())
        h.observe('idle',name+'-reclaimed')
        h.save('runs/'+name+'.json',{'name':name,'workload':work,'mode':mode,'pair':pair,'released_at':release,'completed_at':h.utc(),**data})
        print(json.dumps({'name':name,'result':'PASS'}),flush=True)
    except Exception:
        if created:
            h.save('runs/'+name+'-failure.json',h.iobj('get','pods','-n',h.INNER,'-l','job-name='+name))
            h.inner('delete','job',name,'-n',h.INNER,'--wait=true','--timeout=60s',timeout=80)
        if process and process.poll() is None:process.wait(timeout=260)
        raise
    finally:
        if logfile:logfile.close()

def run():
    if (h.OUT/'started.json').exists():raise RuntimeError('existing run; preserve evidence')
    prepared=json.loads((h.OUT/'prepared.json').read_text())
    c=preflight('before')
    h.save('started.json',{'at':h.utc(),'image':prepared['image'],'pairs':3,'workloads':list(CASES)})
    stop=threading.Event();thread=threading.Thread(target=h.monitor,args=(stop,c['status']['workerPodUID']),daemon=True);thread.start()
    try:
        for work in CASES:
            for pair in (1,2,3):
                for mode in (('pod','guest') if pair==2 else ('guest','pod')):execute(work,mode,pair,prepared['image'])
        h.observe('idle','final-idle')
        h.save('inventory/final-jobs.json',h.iobj('get','jobs','-n',h.INNER,'-l','experiment=transfer-app-20261030'))
        h.save('completed.json',{'at':h.utc(),'result':'PASS','processes':18})
    except Exception as e:
        h.save('failure.json',{'at':h.utc(),'error':repr(e)});raise
    finally:
        stop.set();thread.join(timeout=25);h.snapshot('after')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','run']);p.add_argument('--uploaded',action='store_true',help='resume failed preparation only, before any measurement');a=p.parse_args()
    connect();prepare(a.uploaded) if a.action=='prepare' else run()
