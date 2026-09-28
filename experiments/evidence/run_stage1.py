"""Stage 1 only: three independent request/binding demonstrations, normal drain.

Private VM preparation and SSH keys remain outside the explicitly exported output.
Requires the existing evidence-c28-affinity host-PID helper and released evidence PVC.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import struct
import threading
import time

from campaign_runtime import Run, ROOT, NS, GPU, call, k, get, save


def clean_object(obj, pod=False):
    if not obj:
        return None
    meta = obj['metadata']
    result = {'kind': obj.get('kind'), 'metadata': {key: meta[key] for key in
              ['name', 'namespace', 'uid', 'generation', 'ownerReferences'] if key in meta},
              'status': obj.get('status', {})}
    if pod:
        result['spec'] = {key: obj['spec'].get(key) for key in ['nodeName', 'schedulerName', 'runtimeClassName']}
        result['spec']['containers'] = [{key: c[key] for key in ['name', 'image', 'resources'] if key in c}
                                        for c in obj['spec']['containers']]
        result['metadata']['annotations'] = {key: value for key, value in meta.get('annotations', {}).items()
                                             if 'gpu' in key or 'shm' in key}
    else:
        result['spec'] = obj['spec']
    return result


def validate(snapshot, mapping, runtime, guest):
    q, p, c, w, v = (snapshot[x] for x in ['request', 'profile', 'channel', 'worker', 'vmi'])
    status = c['status']
    quota = {'nvidia.com/gpu': '1', 'nvidia.com/gpumem': '4096', 'nvidia.com/gpucores': '50'}
    resources = w['spec']['containers'][0]['resources']
    observed_quota = {kind: {key: str(value) for key, value in resources[kind].items()}
                      for kind in ['requests', 'limits']}
    mapping_sets = {role: {(x['device'], x['inode']) for row in mapping if row['role'] == role
                          for x in row['backing_mappings']} for role in ['qemu', 'worker']}
    worker_pids = {row['pid'] for row in mapping if row['role'] == 'worker'}
    gpu_pids = {row['pid'] for row in snapshot['gpu_processes'] if row['gpu_uuid'] == GPU}
    checks = {
        'approved_profile': p['spec']['approved'] is True,
        'request_values': q['spec']['count'] == 1 and q['spec']['memory'] == '4096Mi' and q['spec']['compute'] == 50,
        'request_profile_uid': q['spec']['profileRef']['uid'] == p['metadata']['uid'],
        'request_channel_uid': c['spec']['requestRef']['uid'] == q['metadata']['uid'],
        'vm_reference': q['spec']['vmRef'] == c['spec']['vmRef'] and
                        any(o['uid'] == q['spec']['vmRef']['uid'] for o in v['metadata'].get('ownerReferences', [])),
        'vmi_worker_uid': status['vmiUID'] == v['metadata']['uid'] and status['workerPodUID'] == w['metadata']['uid'],
        'ready_mapped': status['phase'] == 'Ready' and len(snapshot['attachments']) == 2 and
                         all(a['status'].get('phase') == 'Mapped' and a['spec']['generation'] == status['generation']
                             for a in snapshot['attachments']),
        'node_matches': status['nodeName'] == p['spec']['nodeName'] == w['spec']['nodeName'] == v['status']['nodeName'],
        'gpu_matches': status['gpuUUID'] == p['spec']['gpuUUID'] == GPU and
                       GPU in w['metadata']['annotations'].get('hami.io/vgpu-devices-allocated', ''),
        'worker_requests_limits': all(observed_quota[kind] == quota for kind in observed_quota),
        'channel_quota': status['memoryMiB'] == 4096 and status['compute'] == 50,
        'hami_loaded': any(any('libvgpu' in path for path in row['library_hashes']) for row in runtime),
        'actual_worker_gpu_process': bool(worker_pids & gpu_pids),
        'same_shared_backing_inode': bool(mapping_sets['worker'] & mapping_sets['qemu']),
        'guest_bar2_mapping': guest['bar2_bytes'] == 64*1024*1024 and bool(guest['probe_bar_maps']),
    }
    return checks


HTML = '''<!doctype html><meta charset="utf-8"><title>Stage 1 | Live evidence</title>
<style>body{background:#101923;color:#e8f1f7;font:19px monospace;margin:25px}h1{font-size:28px}
.grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:18px}.box{background:#192838;padding:18px;border-radius:9px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:16px;line-height:1.4}h2{color:#8ed7ff;font-size:21px}
#result{color:#9aefc0}small{color:#a9bbce}#command{font-size:15px}</style>
<h1>Stage 1 — GPU request to actual VM / Worker / GPU</h1>
<small>Actual command-output viewer | live read-only observations | not a desktop terminal recording</small>
<p id="heading">Waiting for a new run...</p><div class="grid">
<div class="box"><h2>1. Requested resources</h2><pre id="request"></pre></div>
<div class="box"><h2>2. Applied binding</h2><pre id="binding"></pre></div>
<div class="box"><h2>3. Actual GPU execution</h2><pre id="gpu"></pre></div></div>
<h2>Executed command / guest stdout</h2><pre id="command"></pre><pre id="stdout"></pre>
<h2>Verification and normal cleanup</h2><pre id="result"></pre>
<script>function show(id,x){document.getElementById(id).textContent=typeof x==='string'?x:JSON.stringify(x,null,2)}
async function poll(){try{const d=await(await fetch('/state.json',{cache:'no-store'})).json();window.evidence=d;
show('heading',d.run_id+' | '+d.stage+' | observed UTC '+d.utc);show('request',d.request);
show('binding',d.binding);show('gpu',d.gpu);show('command',d.command||'');show('stdout',d.stdout||'');
show('result',{checks:d.checks||{},probe:d.result||{},cleanup:d.cleanup||{}})}catch(e){}setTimeout(poll,750)}poll()</script>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--port', type=int, default=9898)
    parser.add_argument('--prefix', default='evidence-s1-0928')
    args = parser.parse_args()
    if not re.fullmatch('evidence-[a-z0-9-]{1,22}', args.prefix):
        parser.error('Short evidence- prefix required')
    base, public = args.base.resolve(), args.output.resolve()
    for name in ['campaign-probe-guest', 'campaign-probe-native']:
        if not os.access(base/'artifacts'/name, os.X_OK):
            raise ValueError('Executable artifact required before creating a VM: '+name)
    public.mkdir(parents=True, exist_ok=False)
    (public/'runs').mkdir()
    state = {'run_id': 'pending', 'stage': 'PREPARING', 'utc': '', 'request': {}, 'binding': {}, 'gpu': {}}
    state_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            if self.path not in ['/', '/state.json']:
                self.send_error(404)
                return
            with state_lock:
                body = json.dumps(state).encode() if self.path == '/state.json' else HTML.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json' if self.path == '/state.json' else 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def update(**values):
        with state_lock:
            state.update(values, utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
            save(public/'live-state.json', state)

    summary = []
    pre_vmis = json.loads(k(['get', 'vmi', '-A', '-o', 'json']))['items']
    save(public/'existing-vmis-before.json', [{'namespace': v['metadata']['namespace'], 'name': v['metadata']['name'],
          'uid': v['metadata']['uid'], 'phase': v['status']['phase']} for v in pre_vmis])
    deployments = json.loads(k(['get', 'deploy', '-n', NS, '-o', 'json']))['items']
    save(public/'control-images.json', [{ 'name': d['metadata']['name'], 'containers':
          [{'name': x['name'], 'image': x['image']} for x in d['spec']['template']['spec']['containers']]}
          for d in deployments if d['metadata']['name'].startswith('evidence-flyt-')])
    save(public/'protocol.json', {'scope': 'Stage 1 request/binding verification only; no per-request trace or limiter enforcement claim',
         'repeats': 3, 'gpu_uuid': GPU, 'memory_mib': 4096, 'compute': 50, 'sessions': 1,
         'region_bytes': 67108864, 'probe': 'integer resident, 45 seconds after 10-second warmup, 64 inner additions',
         'helper_pod': 'evidence-c28-affinity', 'capture_kind': 'Actual command-output browser viewer',
         'base_commit': call(['git', 'rev-parse', 'HEAD'], cwd=ROOT).strip()})
    try:
        for repeat in range(1, 4):
            name = f'{args.prefix}-{repeat:02d}'
            dest = public/'runs'/name
            dest.mkdir()
            r = Run(base, name, 'shm', 50, phase='I1', repeat=repeat)
            update(run_id=name, stage='PREPARING', request={'count': 1, 'memory': '4096Mi', 'compute': 50},
                   binding={}, gpu={}, checks={}, result={}, cleanup={}, stdout='', command='Preparing new UID-bound VM / Channel')
            failure = None
            snapshot = None
            try:
                r.prepare()
                q, p = get('flytgpurequest', name+'-request'), get('flytgpuprofile', name+'-profile')
                save(dest/'request.json', clean_object(q))
                save(dest/'profile.json', clean_object(p))
                # JSON is also valid YAML 1.2; kubectl output provides familiar YAML for presentation.
                (dest/'request.yaml').write_text(k(['get', 'flytgpurequest', name+'-request', '-n', NS, '-o', 'yaml']))
                update(stage='RUNNING', request={'request': q['metadata']['name'], 'uid': q['metadata']['uid'], **q['spec']})
                with ThreadPoolExecutor(max_workers=1) as pool:
                    job = pool.submit(r.execute, kind='integer', seconds=45, iterations=64, seed=2026+repeat)
                    verified = False
                    while not job.done():
                        t0 = time.time()
                        channel = get('flytsharedmemorychannel', name+'-channel')
                        worker, vmi = get('pod', r.worker), get('vmi', name)
                        attachments = json.loads(k(['get', 'flytchannelattachments', '-n', NS, '-o', 'json']))['items']
                        attachments = [clean_object(a) for a in attachments if a['spec']['channelRef']['uid'] == r.uid]
                        raw_gpu = call(['nvidia-smi', '-i', GPU, '--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory', '--format=csv,noheader,nounits'])
                        gpu_processes = []
                        for line in raw_gpu.splitlines():
                            parts = [x.strip() for x in line.split(',')]
                            if len(parts) == 4:
                                gpu_processes.append({'gpu_uuid': parts[0], 'pid': int(parts[1]), 'process': parts[2], 'memory_mib': parts[3]})
                        snapshot = {'host_start': t0, 'request': clean_object(q), 'profile': clean_object(p),
                                    'channel': clean_object(channel), 'worker': clean_object(worker, True),
                                    'vmi': {'metadata': {key: vmi['metadata'][key] for key in ['name', 'uid', 'ownerReferences']},
                                            'status': vmi['status']}, 'attachments': attachments,
                                    'gpu_processes': gpu_processes, 'host_end': time.time()}
                        with (dest/'snapshots.jsonl').open('a') as stream:
                            stream.write(json.dumps(snapshot)+'\n')
                        stdout = (r.out/'stdout.jsonl').read_text() if (r.out/'stdout.jsonl').exists() else ''
                        command = json.loads((r.out/'command.json').read_text()) if (r.out/'command.json').exists() else {}
                        update(binding={'channel': channel['status']['phase'], 'allocation': channel['status']['allocation'],
                                        'VM': name, 'VMI_UID': vmi['metadata']['uid'], 'VM_node': vmi['status']['nodeName'],
                                        'Worker': r.worker, 'Worker_node': worker['spec']['nodeName'],
                                        'applied': worker['spec']['containers'][0]['resources'],
                                        'attachments': [a['status'].get('phase') for a in attachments]},
                               gpu=gpu_processes, command=command, stdout='\n'.join(stdout.splitlines()[-3:]))
                        if not verified and channel['status']['phase'] == 'Ready' and (r.out/'runtime-libraries.json').exists():
                            identity = json.loads((r.out/'identity.json').read_text())
                            mapping = json.loads(k(['exec', '-i', '-n', NS, 'evidence-c28-affinity', '--', 'python3', '-',
                                                   identity['worker_uid'], identity['launcher_uid'], identity['allocation']],
                                                  input=(ROOT/'experiments/evidence/stage1_host_mapping.py').read_text()))
                            guest_code = """import json
from pathlib import Path
p=Path('/sys/bus/pci/devices')/BDF
parts=(p/'resource').read_text().splitlines()[2].split()
rows=[]
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:
  if b'/tmp/campaign/campaign-probe-guest' not in (proc/'cmdline').read_bytes():continue
  rows += [line for line in (proc/'maps').read_text().splitlines() if BDF in line and 'resource2' in line]
 except (FileNotFoundError,ProcessLookupError):pass
print(json.dumps({'bdf':BDF,'vendor':(p/'vendor').read_text().strip(),'device':(p/'device').read_text().strip(),'bar2_bytes':int(parts[1],16)-int(parts[0],16)+1,'probe_bar_maps':rows}))
"""
                            guest = json.loads(call(r.ssh+['sudo python3 -c '+shlex.quote('BDF='+repr(r.bdf)+'\n'+guest_code)]))
                            runtime = json.loads((r.out/'runtime-libraries.json').read_text())
                            checks = validate(snapshot, mapping, runtime, guest)
                            save(dest/'checks.json', checks)
                            save(dest/'host-mapping.json', mapping)
                            save(dest/'guest-bar.json', guest)
                            save(dest/'applied.json', snapshot)
                            update(checks=checks)
                            verified = all(checks.values())
                        time.sleep(1.5)
                    result = job.result()
                assert verified, 'Stage 1 mapping predicates did not all pass'
                assert result['checked_elements'] == 524288 and result['mismatches'] == 0
                update(stage='PROBE_COMPLETE', result=result, stdout=(r.out/'stdout.jsonl').read_text().splitlines()[-1])
                time.sleep(4)
            except Exception as error:
                failure = str(error)
                save(dest/'failure.json', {'error': failure})
                raise
            finally:
                # Recover exact newly created UID if preparation failed after resource creation.
                if not r.uid:
                    c = get('flytsharedmemorychannel', name+'-channel')
                    if c and (r.out/'private-prepare'/('FlytSharedMemoryChannel-'+name+'-channel.json')).exists():
                        r.uid = c['metadata']['uid']
                r.close()
                for file in ['manifest.json', 'identity.json', 'clock-map.json', 'command.json', 'runtime-libraries.json',
                             'metrics.json', 'stdout.jsonl', 'stderr.txt', 'host-events.jsonl', 'cleanup.json']:
                    if (r.out/file).exists():
                        shutil.copyfile(r.out/file, dest/file)
                if (r.out/'guest-config/binding.json').exists():
                    shutil.copyfile(r.out/'guest-config/binding.json', dest/'binding.json')
                    raw = (r.out/'guest-config/layout.bin').read_bytes()
                    size, sessions = struct.unpack_from('<QI', raw, 32)
                    save(dest/'layout-summary.json', {'region_bytes': size, 'sessions': sessions,
                         'layout_sha256': hashlib.sha256(raw).hexdigest()})
                final = get('flytsharedmemorychannel', name+'-channel')
                save(dest/'channel-final.json', clean_object(final))
                deadline = time.monotonic()+60
                remaining = get('vmi', name) or get('pod', name+'-channel-worker')
                while remaining and time.monotonic() < deadline:
                    time.sleep(1)
                    remaining = get('vmi', name) or get('pod', name+'-channel-worker')
                gpu_after = call(['nvidia-smi', '-i', GPU, '--query-compute-apps=gpu_uuid,pid,process_name', '--format=csv,noheader'])
                cleanup = {'released': bool(final and final['status']['phase'] == 'Released'),
                           'execution_objects_absent': not bool(remaining), 'gpu_processes_after': gpu_after.strip()}
                save(dest/'cleanup-audit.json', cleanup)
                update(stage='RELEASED' if cleanup['released'] else 'CLEANUP_FAILED', cleanup=cleanup)
                assert cleanup['released'] and cleanup['execution_objects_absent'], 'Cleanup incomplete'
            summary.append({'run_id': name, 'stage1': 'PASS', 'allocation': final['status']['allocation'],
                            'generation': final['status']['generation'], 'gpu_uuid': GPU,
                            'correctness': 'PASS', 'cleanup': 'PASS', 'enforcement': 'NOT_EVALUATED'})
            save(public/'summary.json', summary)
            time.sleep(5)
        assert len({r['allocation'] for r in summary}) == 3
        after = json.loads(k(['get', 'vmi', '-A', '-o', 'json']))['items']
        save(public/'existing-vmis-after.json', [{'namespace': v['metadata']['namespace'], 'name': v['metadata']['name'],
              'uid': v['metadata']['uid'], 'phase': v['status']['phase']} for v in after])
        update(stage='COMPLETE', complete=True)
        print('STAGE1_COMPLETE 3/3 independent allocations', flush=True)
        time.sleep(15)
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
