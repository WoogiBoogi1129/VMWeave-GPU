#!/usr/bin/env python3
"""Verify archived publication identities, live policy, correctness and preservation."""
import hashlib
import json
from pathlib import Path

E = Path(__file__).resolve().parent
R = E.parents[3]


def read(name):
    return json.loads((E / name).read_text())


manifest = read('artifacts.json')['sha256']
actual = {str(p.relative_to(E)) for p in E.rglob('*')
          if p.is_file() and p.name != 'artifacts.json'}
assert set(manifest) == actual
for name, digest in manifest.items():
    assert hashlib.sha256((E / name).read_bytes()).hexdigest() == digest, name

release = json.loads((R / 'deploy/releases/v0.5.13.json').read_text())
plugin = json.loads((R / release['devicePluginRecord']).read_text())
assert release == read('release-record.json')
assert release['sourceRevision'] == read('images.json')['sourceRevision']
assert release['images'] == read('images.json')['images']
assert not release['devicePluginRebuilt']
assert release['guestLibrarySHA256'] == plugin['guestLibrarySHA256']
assert plugin['version'] == '0.1.4'
assert release['chart']['version'] == '0.5.13'
assert release['chart']['packageSHA256'] == read('release-assets.json')['sha256']['vmweave-operator-0.5.13.tgz']

v = read('validation.json')
assert v['status'] == 'PASS' and v['policy'] == release['gpuCoreUtilizationPolicy'] == 'default'
assert not v['runtimeSMAdjustmentDeployed'] and not release['runtimeSMAdjustmentDeployed']
assert v['liveComputeModuleAbsent'] and v['crdDynamicFieldsAbsent']
assert not v['performanceMeasurement']
identity = read('published-worker-identity.json')
assert identity['reference'] == v['workerImage'] == release['images']['worker']
assert identity['sourceRevision'] == release['sourceRevision']
assert identity['policy'] == 'default' and identity['liveComputeModuleAbsent']
assert identity['runtimeBinariesUnchanged']
assert (E / 'worker-binaries-before.txt').read_bytes() == (E / 'worker-binaries-after.txt').read_bytes()
assert read('crd-spec-digests.json')['before'] == read('crd-spec-digests.json')['after']

live = read('live-state.json')
assert live['worker']['ready'] and live['worker']['policy'] == 'default'
assert live['worker']['image'] == release['images']['worker']
assert live['worker']['imageID'].split('@')[-1] == release['images']['worker'].split('@')[-1]
assert live['channel']['status']['phase'] == 'Ready'
assert live['vmi']['phase'] == 'Running' and live['vmi']['ready']
assert live['guestAllocatable'] == '1'
assert live['channel']['status']['compute'] == v['reservedCompute'] == 25
assert live['channel']['status']['memoryMiB'] == v['memoryMiB'] == 1024
assert live['channel']['status']['gpuUUID'] == v['gpuUUID']
assert live['channel']['spec']['sessions'] == v['slots'] == 1
assert live['worker']['resources']['limits']['nvidia.com/gpucores'] == '25'

smoke = read('smoke-validation.json')
assert smoke['status'] == 'PASS' and smoke['testNamespaceRemoved']
assert len(smoke['cases']) == 2
for case in smoke['cases']:
    name = case['name']
    assert case['exitCode'] == 0 and case['brokerIdle']
    pod = read(name + '-pod.json')
    assert pod['metadata']['uid'] == case['podUID'] and pod['status']['phase'] == 'Succeeded'
    assert pod['spec']['containers'][0]['image'] == plugin['images']['workload']['runtimeReference']
    assert json.loads((E / (name + '-stdout.txt')).read_text()) == case['result']
    assert case['result']['status'] == 'PASS'
    processes = read(name + '-worker-processes.json')
    assert processes
    for process in processes:
        env = process['environment']
        assert env['GPU_CORE_UTILIZATION_POLICY'] == 'default' and env['CUDA_DEVICE_SM_LIMIT'] == '25'
        assert not any('LIVE_COMPUTE' in key for key in env)
    assert any(p['hamiLibraryMappings'] for p in processes)
assert smoke['cases'][0]['result']['kernel_repeats'] >= 100
assert smoke['cases'][0]['result']['copy_bytes'] == 4096
broker = read('broker-final.json')
assert broker['ready'] and not broker['activeClient'] and broker['maxClients'] == 1
assert broker['librarySHA256'] == release['guestLibrarySHA256']

p = read('preservation.json')
assert p['status'] == 'PASS' and p['protectedRunningPods'] == v['protectedRunningPods']
for key in ['unrelatedPodUIDsAndRestartsUnchanged', 'crdSpecsUnchanged', 'hamiValuesUnchanged',
            'draValuesUnchanged', 'vmIdentityAndDevicesPreserved', 'hostHamiLibraryUnchanged']:
    assert p[key], key
assert not p['privilegedAdministrationPodsCreated']
assert len(p['preExistingUnresolvedChannels']) == 3
assert all(c['phase'] == 'Draining' and c['specUnchanged'] for c in p['preExistingUnresolvedChannels'])
assert read('helm-releases.json') == release['helmReleases']
assert {h['chartVersion'] for h in release['helmReleases']} == {'0.5.13', '0.1.4'}
assert all(h['status'] == 'deployed' for h in release['helmReleases'])
for deployment in read('deployments-after.json'):
    assert deployment['ready'] and deployment['image'] == release['images']['operator']
    assert deployment['imageID'].split('@')[-1] == release['images']['operator'].split('@')[-1]
assert all(run['conclusion'] == 'success' and run['sourceRevision'] == release['sourceRevision']
           for run in read('actions-final.json'))
print(json.dumps(dict(status='PASS',release=release['tag'],policy='default',gpuCases=2,
                      reservedCompute=25,protectedRunningPods=p['protectedRunningPods']),indent=2))
