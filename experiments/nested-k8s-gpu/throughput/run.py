"""One bounded SGEMM comparison on the retained nested cluster. No VM/Operator mutation."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[3]
EXP=ROOT/'experiments/nested-k8s-gpu'
OUT=EXP/'results/20261029-sgemm-throughput'
PRIVATE=ROOT/'.local/nested-k8s-20261028'
REMOTE='/home/ubuntu/nested/sgemm-20261029'
CTX='kubernetes-admin@kubernetes'
NS='vmweave-nested-k8s'
INNER='nested-validation'
VM='vw-k8s-worker-01'
GPU='GPU-7d708c42-8d4a-16d5-0746-474567157aa3'

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def call(args,**kw):return subprocess.check_output([str(x) for x in args],text=True,timeout=kw.pop('timeout',60),**kw)
def k(*args):return call(['kubectl','--context',CTX,'--request-timeout=20s',*args])
def obj(*args):return json.loads(k(*args,'-o','json'))
def save(name,data):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(data if isinstance(data,str) else json.dumps(data,indent=2)+'\n')
SSH=['ssh','-i',str(PRIVATE/'id_ed25519'),'-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o',f'UserKnownHostsFile={PRIVATE}/known_hosts','-o','ConnectTimeout=8']
IPS={}
def sshargs(role,cmd):return SSH+['ubuntu@'+IPS[role],cmd]
def ssh(role,cmd,**kw):return call(sshargs(role,cmd),**kw)
def inner(*args,**kw):return ssh('cp','sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf --request-timeout=20s '+shlex.join(args),**kw)
def iobj(*args):return json.loads(inner(*args,'-o','json'))
def observe(expect,label):
    path=OUT/'observations'/f'{label}.json';path.parent.mkdir(parents=True,exist_ok=True)
    call([sys.executable,EXP/'lab/observe_gpu.py','--context',CTX,'--namespace',NS,'--vm',VM,'--gpu-uuid',GPU,'--expect',expect,'--timeout','60','--output',path],timeout=90)

def snapshot(label):
    channel=obj('get','sharedmemorychannel',VM,'-n',NS)
    save(f'inventory/{label}-channel.json',channel)
    save(f'inventory/{label}-vm-vmi.json',obj('get','vm,vmi','-n',NS))
    save(f'inventory/{label}-inner-nodes.json',iobj('get','nodes'))
    pods=obj('get','pods','-A')['items']
    save(f'inventory/{label}-outer-pods.json',[{'namespace':p['metadata']['namespace'],'name':p['metadata']['name'],'uid':p['metadata']['uid'],'phase':p['status'].get('phase'),'containers':p['status'].get('containerStatuses',[])} for p in pods])
    deployments=obj('get','deployment,daemonset','-A')['items']
    save(f'inventory/{label}-controllers.json',[{'namespace':d['metadata']['namespace'],'name':d['metadata']['name'],'kind':d['kind'],'uid':d['metadata']['uid'],'generation':d['metadata']['generation'],'spec_sha256':hashlib.sha256(json.dumps(d['spec'],sort_keys=True).encode()).hexdigest()} for d in deployments])
    return channel

def monitor(stop,worker_uid):
    with (OUT/'gpu-monitor.jsonl').open('x') as f:
        while not stop.is_set():
            try:
                gpu=call(['nvidia-smi','-i',GPU,'--query-gpu=uuid,utilization.gpu,memory.used,clocks.sm,clocks.mem,power.draw,temperature.gpu','--format=csv,noheader,nounits'],timeout=10).strip()
                apps=call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'],timeout=10)
                rows=[]
                for line in apps.splitlines():
                    v=[x.strip() for x in line.split(',')]
                    if len(v)!=3 or v[0]!=GPU:continue
                    try:cg=Path('/proc/'+v[1]+'/cgroup').read_text()
                    except FileNotFoundError:continue
                    rows.append({'pid':int(v[1]),'memory_mib':v[2],'expected_worker':worker_uid in cg or worker_uid.replace('-','_') in cg})
                result={'at':utc(),'gpu_csv':gpu,'processes':rows}
            except Exception as e:result={'at':utc(),'error':str(e)}
            f.write(json.dumps(result)+'\n');f.flush();stop.wait(1)

def job(name,n,image,gid):
    return {'apiVersion':'batch/v1','kind':'Job','metadata':{'name':name,'namespace':INNER,'labels':{'experiment':'sgemm-20261029'}},'spec':{'backoffLimit':0,'activeDeadlineSeconds':180,'template':{'spec':{
        'restartPolicy':'Never','automountServiceAccountToken':False,'nodeSelector':{'kubernetes.io/hostname':VM},
        'securityContext':{'runAsNonRoot':True,'runAsUser':1000,'runAsGroup':gid,'seccompProfile':{'type':'RuntimeDefault'}},
        'containers':[{'name':'sgemm','image':image,'imagePullPolicy':'Never','args':[str(n),'5','/tmp/sgemm-go',name],
        'env':[{'name':'VMWEAVE_BROKER_SOCKET','value':'/run/vmweave/gpu.sock'},{'name':'LD_LIBRARY_PATH','value':'/opt/vmweave/lib'}],
        'resources':{'requests':{'cpu':'100m','memory':'256Mi'},'limits':{'memory':'1Gi'}},
        'securityContext':{'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}},
        'volumeMounts':[{'name':'broker','mountPath':'/run/vmweave','readOnly':True}]}],
        'volumes':[{'name':'broker','hostPath':{'path':'/run/vmweave','type':'Directory'}}]}}}}

def records(text):return [json.loads(line) for line in text.splitlines() if line.startswith('{')]
def check(text,n):
    rows=records(text);assert any(x['event']=='PASS' for x in rows),'missing PASS'
    checks=[x for x in rows if x['event']=='correctness'];assert len(checks)==3 and all(x['failures']==0 for x in checks)
    results=[x for x in rows if x['event']=='result'];assert len(results)==2
    assert all(x['n']==n and x['seconds']>=5 and x['completed_gemms']>=3 for x in results)
    return rows

def execute(mode,n,pair,image,gid):
    name=f'sgemm29-{n}-{pair}-{mode}'
    if (OUT/f'runs/{name}.json').exists():raise RuntimeError('refuse rerun '+name)
    observe('idle',name+'-before');start=time.monotonic();process=None;created=False
    logpath=OUT/f'runs/{name}.log';logpath.parent.mkdir(parents=True,exist_ok=True)
    try:
        if mode=='guest':
            barrier=REMOTE+'/'+name+'.go'
            command='sg vmweave -c '+shlex.quote('env LD_LIBRARY_PATH=/opt/vmweave/lib VMWEAVE_BROKER_SOCKET=/run/vmweave/gpu.sock timeout -k 10s 180s '+shlex.join([REMOTE+'/sgemm',str(n),'5',barrier,name]))
            with logpath.open('x') as log:
                process=subprocess.Popen(sshargs('worker',command),stdout=log,stderr=subprocess.STDOUT,text=True)
                deadline=time.monotonic()+90
                while not any(x['event']=='ready' for x in records(logpath.read_text())):
                    if process.poll() is not None:raise RuntimeError(name+' ended before ready')
                    if time.monotonic()>deadline:raise TimeoutError(name+' ready')
                    time.sleep(.5)
                observe('active',name+'-active')
                release=utc();ssh('worker','touch '+shlex.quote(barrier))
                rc=process.wait(timeout=160)
                assert rc==0,(name,rc)
        else:
            spec=job(name,n,image,gid);save(f'manifests/{name}.json',spec)
            inner('create','-f','-',input=json.dumps(spec));created=True
            deadline=time.monotonic()+100;pod=None
            while True:
                items=iobj('get','pods','-n',INNER,'-l','job-name='+name)['items']
                if items:
                    pod=items[0]
                    if pod['status']['phase'] in ('Running','Succeeded','Failed'):
                        logs=inner('logs',pod['metadata']['name'],'-n',INNER);logpath.write_text(logs)
                        if any(x['event']=='ready' for x in records(logs)):break
                        if pod['status']['phase'] in ('Succeeded','Failed'):raise RuntimeError(name+' ended before ready')
                if time.monotonic()>deadline:raise TimeoutError(name+' ready')
                time.sleep(1)
            save(f'runs/{name}-pod-start.json',pod)
            observe('active',name+'-active');release=utc()
            inner('exec',pod['metadata']['name'],'-n',INNER,'--','touch','/tmp/sgemm-go')
            try:inner('wait','-n',INNER,'job/'+name,'--for=condition=Complete','--timeout=160s',timeout=180)
            finally:
                logpath.write_text(inner('logs',pod['metadata']['name'],'-n',INNER))
                save(f'runs/{name}-pod-final.json',iobj('get','pod',pod['metadata']['name'],'-n',INNER))
        rows=check(logpath.read_text(),n)
        observe('idle',name+'-reclaimed')
        result={'name':name,'mode':mode,'n':n,'pair':pair,'released_at':release,'completed_at':utc(),'orchestration_seconds_including_barrier':time.monotonic()-start,'records':rows}
        save(f'runs/{name}.json',result)
        print(json.dumps({'name':name,'result':'PASS','metrics':[x for x in rows if x['event']=='result']}),flush=True)
    except Exception:
        if mode=='pod' and created:
            save(f'runs/{name}-failure-state.json',iobj('get','pods','-n',INNER,'-l','job-name='+name))
            inner('delete','job',name,'-n',INNER,'--wait=true','--timeout=60s',timeout=80)
        if process and process.poll() is None:
            # Remote GNU timeout bounds the actual workload even if SSH disconnects.
            process.wait(timeout=200)
        raise

def main():
    prepared='--prepared' in sys.argv
    if (OUT/'started.json').exists():raise SystemExit('Existing run: inspect evidence instead of rerunning')
    OUT.mkdir(parents=True,exist_ok=True)
    for role,name in [('cp','vw-k8s-cp-01'),('worker',VM)]:IPS[role]=obj('get','svc',name,'-n',NS)['spec']['clusterIP']
    channel=snapshot('before-measurement' if prepared else 'before');assert channel['status']['phase']=='Ready' and channel['status']['gpuUUID']==GPU
    nodes=iobj('get','nodes')['items'];assert len(nodes)==2 and all(any(c['type']=='Ready' and c['status']=='True' for c in n['status']['conditions']) for n in nodes)
    observe('idle','preflight-prepared' if prepared else 'preflight')
    apps=call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader']);assert GPU not in apps,'target GPU already in use'
    save('inventory/guest-environment'+('-prepared' if prepared else '')+'.txt',ssh('worker','uname -a; ldd --version | head -1; id; getent group vmweave; sha256sum /opt/vmweave/lib/libvmweave_guest.so; sudo systemctl is-active vmweave-guest-broker kubelet crio'))
    gid=int(ssh('worker','getent group vmweave').split(':')[2]);assert gid==998
    if not prepared:
        ssh('worker','test ! -e '+REMOTE+' && mkdir -m 755 '+REMOTE)
        for name in ('sgemm.c','Containerfile'):
            ssh('worker','cat > '+REMOTE+'/'+name,input=(EXP/'throughput'/name).read_text())
        build=f'cd {REMOTE} && cp /opt/vmweave/lib/libvmweave_guest.so . && gcc -std=c11 -O2 -Wall -Wextra -Werror sgemm.c -L. -lvmweave_guest -lm -o sgemm && sudo podman build --pull=false -t localhost/nested-sgemm:20261029 -f Containerfile . && sha256sum sgemm libvmweave_guest.so'
        save('build.log',ssh('worker',build,stderr=subprocess.STDOUT,timeout=180))
    else:
        assert ssh('worker','cat '+REMOTE+'/sgemm.c')==(EXP/'throughput/sgemm.c').read_text(),'prepared source mismatch'
    metadata=json.loads(ssh('worker','sudo podman image inspect localhost/nested-sgemm:20261029'))[0]
    if prepared:assert metadata['Id']==json.loads((OUT/'inventory/image.json').read_text())['Id']
    else:save('inventory/image.json',metadata)
    image=metadata['RepoDigests'][0]
    hashes=ssh('worker',f'cd {REMOTE} && sha256sum sgemm libvmweave_guest.so; sudo podman run --rm --network=none --entrypoint /usr/bin/sha256sum '+shlex.quote(image)+' /opt/vmweave/bin/sgemm /opt/vmweave/lib/libvmweave_guest.so')
    save('inventory/binary-library.sha256',hashes)
    lines=hashes.splitlines();assert len(lines)==4 and lines[0].split()[0]==lines[2].split()[0] and lines[1].split()[0]==lines[3].split()[0]
    save('started.json',{'at':utc(),'source_git':call(['git','rev-parse','HEAD']).strip(),'image':image,'gpu':GPU,'sizes':[1024,4096],'pairs':3})
    stop=threading.Event();thread=threading.Thread(target=monitor,args=(stop,channel['status']['workerPodUID']),daemon=True);thread.start()
    try:
        for n in (1024,4096):
            for pair in (1,2,3):
                for mode in (('pod','guest') if pair==2 else ('guest','pod')):execute(mode,n,pair,image,gid)
        save('completed.json',{'at':utc(),'result':'PASS','runs':12})
    except Exception as e:
        save('failure.json',{'at':utc(),'error':repr(e)});raise
    finally:
        stop.set();thread.join(timeout=25);snapshot('after')

if __name__=='__main__':main()
