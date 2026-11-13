#!/usr/bin/env python3
"""Render/run one isolated forward probe. Does not deploy or restart a VM.

Uses the published v0.5.9 template; candidate Guest requires an explicitly
identified, ready candidate Worker. Connection JSON stays in .local/.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import time

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
TEMPLATE = REPO/'deploy/releases/evidence/v0.5.9/training/published-basic/submitted.json'

def paired_worker_ready(worker, expected):
    # CRI-O may show a local tag in status.image even when spec pins a digest.
    # Verify the running imageID and the matching spec container by name.
    if '@sha256:' not in expected:
        return False
    digest = expected.rsplit('@', 1)[1]
    names = {x['name'] for x in worker['spec']['containers'] if x['image']==expected}
    return any(x['name'] in names and x.get('ready') and 'running' in x.get('state', {})
               and x.get('imageID', '').removeprefix('docker-pullable://').rsplit('@', 1)[-1]==digest
               for x in worker.get('status', {}).get('containerStatuses', []))

def main(workload_root=HERE, namespace_prefix='cnn-forward-',
         cases=('minimal','matrix','stream'), pod_deadline=240):
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['render', 'run', 'collect'])
    p.add_argument('--connection', type=Path, required=True)
    p.add_argument('--results', type=Path, required=True)
    p.add_argument('--name', required=True)
    p.add_argument('--mode', choices=['cpu', 'gpu'], default='gpu')
    p.add_argument('--backend', choices=['legacy', 'default'], required=True)
    p.add_argument('--case', choices=cases, default='minimal')
    p.add_argument('--guest-library', type=Path)
    p.add_argument('--worker-image', help='Required with candidate Guest; exact paired Worker image')
    p.add_argument('--loader-trace', action='store_true')
    a = p.parse_args()
    if a.guest_library and not a.worker_image:
        p.error('candidate Guest requires --worker-image')
    if a.worker_image and not a.guest_library:
        p.error('--worker-image requires a paired --guest-library')
    c = json.loads(a.connection.read_text())
    ns = c['namespace']; runid = c['runID']
    assert ns.startswith(namespace_prefix) and runid.startswith(namespace_prefix)
    assert a.name and len(a.name)<=40 and all(ch in 'abcdefghijklmnopqrstuvwxyz0123456789-' for ch in a.name)
    d = a.results/a.name
    d.mkdir(parents=True, exist_ok=a.action=='collect')
    def k(*args, data=None, check=True):
        cmd = shlex.join(['kubectl', '--context', c['context'], '--request-timeout=30s', *args])
        r = subprocess.run(c['sshArgv']+[cmd], input=data, capture_output=True, text=True, timeout=45)
        if check and r.returncode:
            raise RuntimeError(r.stderr)
        return r
    def save(name, obj):
        (d/name).write_text(json.dumps(obj, indent=2)+'\n')
    def collect():
        pod = json.loads(k('-n', ns, 'get', 'pod', a.name, '-o', 'json').stdout)
        assert pod['metadata']['labels']['vmweave-experiment']==runid
        save('pod.json', pod)
        logs = k('-n', ns, 'logs', a.name, '-c', 'pytorch', check=False)
        ordinary = []
        for line in logs.stdout.splitlines():
            if not line.startswith('CNN_ARTIFACT '):
                ordinary.append(line); continue
            artifact = json.loads(line.removeprefix('CNN_ARTIFACT ')); name = artifact['name']
            assert Path(name).name==name and name not in ('pod.json','submitted.json','code.json','identity.json','worker.json','channel.json','guest.json')
            data = base64.b64decode(artifact['base64'], validate=True)
            assert hashlib.sha256(data).hexdigest()==artifact['sha256']
            (d/name).write_bytes(data)
        (d/'pod-log.txt').write_text('\n'.join(ordinary)+'\n'+logs.stderr)
        (d/'describe.txt').write_text(k('-n', ns, 'describe', 'pod', a.name).stdout)
        return pod
    if a.action=='collect':
        collect(); return
    supervisor=workload_root/'workloads/supervise.py'
    if not supervisor.exists():supervisor=HERE.parent/'cnn-preflight/workloads/supervise.py'
    sources = {'probe.py': (workload_root/'workloads/probe.py').read_text(),
               'supervise.py': supervisor.read_text()}
    code = dict(apiVersion='v1', kind='ConfigMap', metadata=dict(name='code-'+a.name, namespace=ns), immutable=True, data=sources)
    save('code.json', code)
    obj = json.loads(TEMPLATE.read_text())
    obj['metadata'] = dict(name=a.name, namespace=ns, labels={'vmweave-experiment': runid})
    spec = obj['spec']; spec['activeDeadlineSeconds']=pod_deadline
    spec['nodeSelector']={'kubernetes.io/hostname':c['node']}
    spec['securityContext']['supplementalGroups']=[c['brokerGID']]
    app = spec['containers'][0]
    argv = ['python','-u','/work/supervise.py','--mode',a.mode,'--backend',a.backend,'--case',a.case]
    app['args']=['export LD_LIBRARY_PATH="/opt/vmweave/adapter${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"; exec '+shlex.join(argv)]
    app['env']=[e for e in app['env'] if e['name'] not in ('DISABLE_ADDMM_CUDA_LT','TORCH_CUDNN_V8_API_DISABLED','RNN_LOADER_TRACE')]
    app['env'] += [dict(name='CNN_LOADER_TRACE', value='1' if a.loader_trace else '0'),dict(name='PYTHONFAULTHANDLER',value='1')]
    for v in spec['volumes']:
        if v['name']=='code': v['configMap']['name']='code-'+a.name
    guest = None
    if a.guest_library and a.mode=='gpu':
        payload = a.guest_library.read_bytes(); digest=hashlib.sha256(payload).hexdigest()
        guest = dict(apiVersion='v1',kind='ConfigMap',metadata=dict(name='guest-'+a.name,namespace=ns),immutable=True,
                     binaryData={'libvmweave_guest.so':base64.b64encode(payload).decode()})
        save('guest.json',guest)
        spec['volumes'].append(dict(name='candidate',configMap=dict(name='guest-'+a.name)))
        init=spec['initContainers'][0]
        init['volumeMounts'].append(dict(name='candidate',mountPath='/candidate',readOnly=True))
        init['args']=['cp /candidate/libvmweave_guest.so /adapter/; cd /adapter; echo '+shlex.quote(digest+'  libvmweave_guest.so')+' | sha256sum -c -; ln -s libvmweave_guest.so libcuda.so.1; chmod 0555 libvmweave_guest.so']
    else:
        digest=json.loads((REPO/'deploy/releases/v0.5.9.json').read_text())['guestLibrarySHA256']
    if a.mode=='cpu':
        spec.pop('initContainers',None)
        spec['volumes']=[v for v in spec['volumes'] if v['name']!='adapter']
        app['volumeMounts']=[v for v in app['volumeMounts'] if v['name']!='adapter']
        app['env']=[e for e in app['env'] if e['name'] not in ('LD_PRELOAD','VMWEAVE_MIRROR_DEVICE_VA')]
        app['resources']['limits'].pop('vmweave.io/gpu',None)
        app['args']=['exec '+shlex.join(argv)]
    save('submitted.json',obj)
    worker_image=a.worker_image or json.loads((REPO/'deploy/releases/v0.5.9.json').read_text())['images']['worker']
    save('identity.json',dict(sourceSHA256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()},
         guestLibrarySHA256=digest if a.mode=='gpu' else None,expectedWorkerImage=worker_image,
         templateSHA256=hashlib.sha256(TEMPLATE.read_bytes()).hexdigest(),rtol=1e-4,atol=1e-6,backend=a.backend))
    if a.action=='render':
        print('rendered',d); return
    # Read host state before any namespace/Pod mutations. Never repair a
    # Draining channel, bypass finalizers, or replace the runtime from this tool.
    if a.mode=='gpu':
        raw=subprocess.check_output(['kubectl','-n','vmweave-test-b','get','sharedmemorychannel','dp-dev-20261105','-o','json'],text=True)
        channel=json.loads(raw);save('channel.json',channel)
        if channel['status']['phase']!='Ready':
            save('preflight.json',dict(status='BLOCKED',phase=channel['status']['phase'],
                 reason=channel['status'].get('reason'),podCreated=False))
            raise SystemExit('BLOCKED: test Channel is '+channel['status']['phase']+'; no Pod created')
        pods=json.loads(subprocess.check_output(['kubectl','-n','vmweave-test-b','get','pods','-o','json'],text=True))['items']
        worker=next(x for x in pods if x['metadata']['uid']==channel['status']['workerPodUID'])
        save('worker.json',worker)
        assert paired_worker_ready(worker, worker_image), 'paired Worker digest is not ready'
    existing=k('get','namespace',ns,'--ignore-not-found','-o','json').stdout
    if existing:
        assert json.loads(existing)['metadata']['labels']['vmweave-experiment']==runid
    else:
        k('create','-f','-',data=json.dumps(dict(apiVersion='v1',kind='Namespace',metadata=dict(name=ns,labels={'vmweave-experiment':runid}))))
    # Namespace creation precedes the controller-created default account.
    account_deadline=time.monotonic()+60
    while not k('-n',ns,'get','serviceaccount','default','--ignore-not-found','-o','name').stdout.strip():
        if time.monotonic()>=account_deadline:
            raise RuntimeError('default ServiceAccount was not created within 60 seconds')
        time.sleep(1)
    active=json.loads(k('get','pods','-A','-o','json').stdout)['items']
    assert not [x for x in active if x['status']['phase'] not in ('Succeeded','Failed') and any(y.get('resources',{}).get('limits',{}).get('vmweave.io/gpu') for y in x['spec']['containers'])], 'another GPU Pod is active'
    for resource in [code]+([guest] if guest else [])+[obj]:
        k('create','-f','-',data=json.dumps(resource))
    deadline=time.monotonic()+pod_deadline+60
    while time.monotonic()<deadline:
        pod=json.loads(k('-n',ns,'get','pod',a.name,'-o','json').stdout)
        if pod['status']['phase'] in ('Succeeded','Failed'):break
        time.sleep(2)
    pod=collect()
    result=json.loads((d/'exit.json').read_text())
    print(json.dumps(dict(phase=pod['status']['phase'],child=result)))
    if pod['status']['phase']!='Succeeded' or result['returncode']!=0 or result['timeout']:
        raise SystemExit(1)

if __name__=='__main__':
    main()
