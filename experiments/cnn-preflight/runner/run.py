#!/usr/bin/env python3
"""Run isolated diagnostic Pods using the previously validated image manifest."""
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import time

HERE = Path(__file__).resolve().parents[1]
TEMPLATE = HERE.parent/'device-plugin-pytorch/results/20261106-official/torch-gpu-compat/submitted.json'

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--connection', type=Path, required=True)
    p.add_argument('--results', type=Path, required=True)
    p.add_argument('action', choices=['prepare', 'run', 'collect'])
    p.add_argument('--name')
    p.add_argument('--mode', choices=['cpu', 'gpu'], default='gpu')
    p.add_argument('--case', choices=['basic', 'all', 'conv-forward', 'conv-train', 'conv-bn', 'cudnn-stream'], default='conv-forward')
    p.add_argument('--loader-trace', action='store_true')
    p.add_argument('--code-map', default='cnn-code')
    p.add_argument('--stream-trace', action='store_true')
    a = p.parse_args(); c = json.loads(a.connection.read_text()); a.results.mkdir(exist_ok=True, parents=True)
    ns = c['namespace']; runid = c['runID']
    assert ns.startswith('cnn-preflight-') and runid.startswith('cnn-preflight-')

    def k(*argv, data=None, check=True):
        command = shlex.join(['kubectl', '--context', c['context'], '--request-timeout=30s', *argv])
        r = subprocess.run(c['sshArgv']+[command], input=data, text=True, capture_output=True, timeout=45)
        if check and r.returncode: raise RuntimeError(r.stderr)
        return r

    def create(obj):
        return k('create', '-f', '-', data=json.dumps(obj))

    def collect(name):
        d = a.results/name; d.mkdir(exist_ok=True)
        pod = json.loads(k('-n', ns, 'get', 'pod', name, '-o', 'json').stdout)
        assert pod['metadata']['labels']['vmweave-experiment'] == runid
        (d/'pod.json').write_text(json.dumps(pod, indent=2)+'\n')
        logs = k('-n', ns, 'logs', name, '-c', 'pytorch', check=False)
        ordinary = []
        for line in logs.stdout.splitlines():
            if line.startswith('CNN_ARTIFACT '):
                artifact = json.loads(line[len('CNN_ARTIFACT '):]); filename = artifact['name']
                assert Path(filename).name == filename and filename not in ['pod.json', 'submitted.json']
                data = base64.b64decode(artifact['base64'], validate=True)
                assert hashlib.sha256(data).hexdigest() == artifact['sha256']
                (d/filename).write_bytes(data)
            else: ordinary.append(line)
        (d/'pod-log.txt').write_text('\n'.join(ordinary)+'\n'+logs.stderr)
        (d/'describe.txt').write_text(k('-n', ns, 'describe', 'pod', name).stdout)
        if pod['spec'].get('initContainers'):
            (d/'guest-adapter.txt').write_text(k('-n', ns, 'logs', name, '-c', 'guest-adapter', check=False).stdout)
        result = json.loads((d/'exit.json').read_text()) if (d/'exit.json').exists() else None
        print(json.dumps(dict(pod=name, phase=pod['status']['phase'], child=result)), flush=True)
        return pod, result

    if a.action == 'prepare':
        sources = {f.name:f.read_text() for f in (HERE/'workloads').glob('*.py')}
        create(dict(apiVersion='v1', kind='Namespace', metadata=dict(name=ns, labels={'vmweave-experiment':runid})))
        create(dict(apiVersion='v1', kind='ConfigMap', metadata=dict(name=a.code_map, namespace=ns), immutable=True, data=sources))
        protocol = dict(namespace=ns, runID=runid, template=str(TEMPLATE.relative_to(HERE.parent.parent)),
                        templateSHA256=hashlib.sha256(TEMPLATE.read_bytes()).hexdigest(),
                        sourceSHA256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()},
                        seed=20261107, rtol=1e-4, atol=1e-6, inputShape=[2,3,8,8],
                        conv=dict(outChannels=4, kernel=3, padding=1, bias=True), steps=3,
                        timeoutSeconds=120, benchmark=False, cpuFallback=False)
        (a.results/'protocol.json').write_text(json.dumps(protocol, indent=2)+'\n')
        print('prepared', ns); return
    assert a.name
    owner = json.loads(k('get', 'ns', ns, '-o', 'json').stdout)
    assert owner['metadata']['labels']['vmweave-experiment'] == runid
    if a.action == 'run':
        active = json.loads(k('get', 'pods', '-A', '-o', 'json').stdout)['items']
        assert not [pod['metadata']['name'] for pod in active if pod['status']['phase'] not in ['Succeeded','Failed'] and any(con.get('resources',{}).get('limits',{}).get('vmweave.io/gpu') for con in pod['spec']['containers'])], 'another GPU Pod is active'
        obj = copy.deepcopy(json.loads(TEMPLATE.read_text()))
        obj['metadata'] = dict(name=a.name, namespace=ns, labels={'vmweave-experiment':runid})
        spec = obj['spec']; spec['activeDeadlineSeconds'] = 240
        spec['nodeSelector'] = {'kubernetes.io/hostname':c['node']}
        spec['securityContext']['supplementalGroups'] = [c['brokerGID']]
        app = spec['containers'][0]
        argv = ['python','-u','/work/supervise.py','--mode',a.mode,'--case',a.case]
        app['args'] = ['export LD_LIBRARY_PATH="/opt/vmweave/adapter${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"; exec '+shlex.join(argv)]
        app['env'] += [{'name':'CNN_LOADER_TRACE','value':'1' if a.loader_trace else '0'}, {'name':'PYTHONFAULTHANDLER','value':'1'}]
        if a.stream_trace:
            assert a.mode == 'gpu'
            next(e for e in app['env'] if e['name'] == 'LD_PRELOAD')['value'] = '/work/trace-stream.so:/opt/vmweave/adapter/libvmweave_guest.so'
        for vol in spec['volumes']:
            if vol['name'] == 'code': vol['configMap']['name'] = a.code_map
        if a.mode == 'cpu':
            spec.pop('initContainers', None)
            spec['volumes'] = [v for v in spec['volumes'] if v['name'] != 'adapter']
            app['volumeMounts'] = [v for v in app['volumeMounts'] if v['name'] != 'adapter']
            app['env'] = [e for e in app['env'] if e['name'] not in ['LD_PRELOAD','VMWEAVE_MIRROR_DEVICE_VA']]
            app['resources']['limits'].pop('vmweave.io/gpu', None)
            app['args'] = ['exec '+shlex.join(argv)]
        d = a.results/a.name; d.mkdir(exist_ok=False)
        (d/'submitted.json').write_text(json.dumps(obj, indent=2)+'\n')
        print(create(obj).stdout.strip(), flush=True)
        deadline = time.monotonic()+300
        while time.monotonic() < deadline:
            pod = json.loads(k('-n', ns, 'get', 'pod', a.name, '-o', 'json').stdout)
            if pod['status']['phase'] in ['Succeeded','Failed']: break
            time.sleep(2)
        else:
            collect(a.name); raise TimeoutError('diagnostic Pod deadline')
    pod, result = collect(a.name)
    if not result or result['returncode'] != 0 or result['timeout']: raise SystemExit(1)

if __name__ == '__main__':
    main()
