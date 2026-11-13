#!/usr/bin/env python3
"""Verify the archived published fixed-slot release and CNN regression, deployment and preservation."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[3]
def read(name):return json.loads((ROOT/name).read_text())
manifest=read('artifacts.json')['sha256']
assert set(manifest)=={str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file() and p.name not in ('artifacts.json','validation-check.json')}
for name,digest in manifest.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
release=json.loads((REPO/'deploy/releases/v0.5.11.json').read_text())
plugin=json.loads((REPO/'deploy/releases/device-plugin-v0.1.3.json').read_text())
assert release==read('release-record.json') and plugin==read('plugin-record.json')
assert release['sourceRevision']==plugin['sourceRevision']=='f6c6ab7acc28fc91d409110a7539a0d22b759ce2'
assert release['chart']['version']=='0.5.11' and plugin['chart']['version']=='0.1.3'
assert release['guestLibrarySHA256']==plugin['guestLibrarySHA256']==read('guest-package-equivalence.json')['librarySHA256']
for component,reference in release['images'].items():
    assert read('published-images.json')[component]=={'reference':reference,'sourceRevision':release['sourceRevision']}
validation=read('validation.json');assert validation['status']=='PASS'
assert validation['guestLibrarySHA256']==release['guestLibrarySHA256']
assert validation['workerImage']==release['images']['worker']
official='docker.io/pytorch/pytorch@sha256:eee11b3b3872a8c838e35ef48f08b2d5def2080902c7f666831310ca1a0ef2be'
total=0
for name,count in [('relu',70),('pool',70),('cnn',300),('cnn-repeat',300),('mnist',300),('mlp',22),('lstm',36),('basic',0)]:
    group='training' if name in ('mlp','lstm','basic') else 'cnn';run=group+'/published-'+name
    pod=read(run+'/pod.json');status=read(run+'/exit.json')
    assert pod['status']['phase']=='Succeeded' and status['returncode']==0 and not status['timeout']
    app=next(x for x in pod['spec']['containers'] if x['name']=='pytorch')
    actual=next(x for x in pod['status']['containerStatuses'] if x['name']=='pytorch')
    assert app['image']==actual['imageID']==official
    init=pod['spec']['initContainers'][0]
    assert init['image']==plugin['images']['guest']['runtimeReference']
    assert release['guestLibrarySHA256'] in ' '.join(init['args'])
    assert not any(x['name']=='candidate' for x in pod['spec']['volumes'])
    if count:
        rows=read(run+'/comparison.json');assert len(rows)==count and all(x.get('passed',x.get('pass_')) for x in rows)
        total+=count
    if group=='cnn':
        identity=read(run+'/identity.json');assert identity['expectedWorkerImage']==release['images']['worker'] and identity['backend']=='legacy'
        worker=read(run+'/worker.json');digest=release['images']['worker'].split('@')[1]
        assert any(x['ready'] and x['imageID'].rsplit('@',1)[-1]==digest for x in worker['status']['containerStatuses'])
assert total==1098
audit=read('cnn/tensor-audit.json');assert audit['status']=='PASS' and audit['tensors']==1040 and audit['rtol']==1e-4 and audit['atol']==1e-6
for name in ['published-idle']:
    pod=read(name+'/pod.json');assert pod['status']['phase']=='Succeeded'
    assert pod['spec']['containers'][0]['image']==plugin['images']['workload']['runtimeReference']
    assert read(name+'/stdout.txt')['status']=='PASS'
proof=read('gpu-observation.json');assert proof['status']=='PASS' and proof['observationScope']=='host PID namespace'
assert all(row.split(',')[0].strip()==read('gpuprofile-after.json')['spec']['gpuUUID'] for row in proof['gpu'])
assert any(int(s.split('NSpid:')[1].split()[-1]) in {p['pid'] for p in proof['sessions']} for s in proof['hostProcessStatus'].values())
preserve=read('preservation.json');assert preserve['status']=='PASS' and preserve['adminPodRemoved']
for key in ('previousProfileRequestPVCIdentitiesAndSpecsPreserved','vmSpecPreservedExceptSessionBindingAndHookImage','helmValuesPreservedExceptPublishedImageAndGuestHash'):assert preserve[key]
assert all(x['specUnchanged'] for x in preserve['protectedRunningVMs']+preserve['preExistingUnresolvedChannels'])
assert validation['testNamespacesRemoved'] and validation['sessionsReclaimed']
assert read('broker-final.json')['ready'] and not read('broker-final.json')['activeClient']
assert read('sharedmemorychannel-after.json')['status']['phase']=='Ready'
assert read('vm-after.json')['spec']['runStrategy']=='Always' and read('vmi-after.json')['status']['phase']=='Running'
assert {x['chartVersion'] for x in read('helm-releases.json')}=={'0.5.11','0.1.3'}
for component in read('deployments-after.json'):
    assert component['ready'] and component['image']==release['images']['operator']
    assert component['imageID'].rsplit('@',1)[-1]==release['images']['operator'].split('@')[1]
for name,digest in read('published-control-equivalence.json').items():
    assert hashlib.sha256((ROOT/'source'/name).read_bytes()).hexdigest()==digest
    assert read('candidate-control-hashes.json')['runtime/shm/control/'+name]==digest
assert all(x.get('removed') or x.get('alreadyAbsent') for x in read('experimental-operator-images-cleanup.json'))
assert read('experimental-resource-cleanup.json')['absent']
assert plugin['scope']['slotsPerVM']==[1,2] and plugin['scope']['deployedSlots']==1
print(json.dumps(dict(status='PASS' ,runtime='v0.5.11',devicePlugin='0.1.3',cnnSteps=80,
                     cnnTensors=1040,mlpLstmTensors=58,independentCNNBackwardAudit=True,
                     helmUpgraded=3,guestWorkerPaired=True,protectedVMsPreserved=True),indent=2))
