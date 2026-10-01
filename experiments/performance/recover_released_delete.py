"""One-channel administrative recovery after foreground GC removed detach records.

This is explicitly a manual finalizer release, not new detach evidence. It is
limited to a previously committed Released record and an empty, idle allocation.
"""
import hashlib
from common import *

name = 'perf-c-r1-100'
folder = OUT / 'cleanup-recovery'
folder.mkdir(exist_ok=True)
source = OUT / 'runs' / name / 'channel-released.json'
historical = call(['git', 'show', '67cffa2:' + str(source.relative_to(ROOT))])
assert source.read_text() == historical
old = json.loads(historical)
assert old['status']['phase'] == 'Released'
assert old['status']['reason'] == 'DetachAndReclamationConfirmed'
current = get('sharedmemorychannels.vmweave.io', name)
assert current['metadata']['uid'] == old['metadata']['uid']
assert current['metadata'].get('deletionTimestamp')
assert current['status']['reason'] == 'AwaitingDetachEvidence'
assert current['spec'] == old['spec']
for field in ['allocation', 'generation', 'gpuUUID', 'workerPodUID', 'vmiUID']:
    assert current['status'][field] == old['status'][field]
vm = get('vm', name)
assert vm['metadata']['uid'] == old['spec']['vmRef']['uid']
assert vm['spec']['runStrategy'] == 'Halted'
assert not get('vmi', name)
pvc = get('pvc', name)
assert pvc['metadata']['uid'] == old['spec']['pvcRef']['uid']
pv = get('pv', pvc['spec']['volumeName'], 'default')
backing = '/var/lib/vmweave/performance-20260930/' + name
assert pv['spec']['local']['path'] == backing
pods = json.loads(k('get', 'pods', '-n', NS, '-o', 'json'))['items']
holders = [p for p in pods if any(v.get('persistentVolumeClaim', {}).get('claimName') == name
                                for v in p['spec'].get('volumes', []))]
assert not holders
assert not any(p['metadata']['uid'] == old['status']['workerPodUID'] for p in pods)
gpu = call(['nvidia-smi', '-i', GPU, '--query-compute-apps=pid,process_name', '--format=csv,noheader']).strip()
assert not gpu
contents = admin(['find', '/host' + backing, '-mindepth', '1', '-maxdepth', '1', '-print']).strip()
assert not contents
node = get('node', 'gpu-4', 'default')
assert any(c['type'] == 'Ready' and c['status'] == 'True' for c in node['status']['conditions'])
save(folder / 'manual-finalization-preconditions.json', {
    'utc': time.time(), 'channel': current, 'historical_release_commit': '67cffa2',
    'historical_release_sha256': hashlib.sha256(historical.encode()).hexdigest(),
    'vm': vm, 'pvc': pvc, 'pv': pv, 'pvc_holders': holders,
    'target_gpu_processes': gpu, 'backing_contents': contents, 'node_ready': True,
    'scope': 'One already Released allocation. No new attachment/measurement success records are synthesized.'})
current = get('sharedmemorychannels.vmweave.io', name)
assert current['metadata']['finalizers'] == ['vmweave.io/shm-detach']
patch = [{'op': 'test', 'path': '/metadata/uid', 'value': old['metadata']['uid']},
         {'op': 'test', 'path': '/metadata/resourceVersion', 'value': current['metadata']['resourceVersion']},
         {'op': 'test', 'path': '/metadata/finalizers', 'value': ['vmweave.io/shm-detach']},
         {'op': 'remove', 'path': '/metadata/finalizers/0'}]
k('patch', 'sharedmemorychannels.vmweave.io', name, '-n', NS, '--type=json', '-p', json.dumps(patch))
wait(lambda: not get('sharedmemorychannels.vmweave.io', name), 30)
save(folder / 'manual-finalization-result.json', {
    'utc': time.time(), 'channel': name, 'uid': old['metadata']['uid'], 'deleted': True,
    'method': 'Explicit manual finalizer release after committed historical release and live idle/empty allocation checks',
    'measurement_changed': False})
print('One previously Released channel administratively finalized; evidence retained.')
