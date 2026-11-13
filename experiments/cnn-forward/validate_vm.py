#!/usr/bin/env python3
"""Audit the completed VM run, including failures, actual calls and restoration."""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent/'results/20261113-vm'
def read(name):return json.loads((ROOT/name).read_text())
manifest=read('artifacts.json')
for name,digest in manifest['sha256'].items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
expected_image='docker.io/pytorch/pytorch@sha256:eee11b3b3872a8c838e35ef48f08b2d5def2080902c7f666831310ca1a0ef2be'
successful=['baseline-cpu','baseline-stream','candidate-stream-v1','candidate-minimal',
            'candidate-matrix','candidate-matrix-repeat','regression/candidate-mlp',
            'regression/candidate-lstm','regression/candidate-lstm-repeat',
            'regression/candidate-basic-after','regression/restored-published-basic']
failed=['baseline-default','baseline-legacy','candidate-default']
candidate=read('candidate-artifact-identity.json')
public=read('restoration.json')['publishedGuestSHA256']
for run in successful+failed:
    pod=read(run+'/pod.json');status=read(run+'/exit.json')
    app=next(x for x in pod['spec']['containers'] if x['name']=='pytorch')
    actual=next(x for x in pod['status']['containerStatuses'] if x['name']=='pytorch')
    assert app['image']==actual['imageID']==expected_image,run
    assert not status['timeout']
    if run in successful:
        assert status['returncode']==0 and pod['status']['phase']=='Succeeded',run
    else:
        assert status['returncode']==-11 and status['signal']==11 and pod['status']['phase']=='Failed',run
    if 'candidate-' in run:
        init=pod['spec']['initContainers'][0]
        assert candidate['guestLibrarySHA256'] in ' '.join(init['args']),run
    if run=='regression/restored-published-basic':
        assert public in ' '.join(pod['spec']['initContainers'][0]['args'])

comparisons=0
for run,count in [('candidate-minimal',6),('candidate-matrix',96),('candidate-matrix-repeat',96)]:
    rows=read(run+'/comparison.json');assert len(rows)==count and all(x['passed'] for x in rows)
    assert {x['key'].split('/')[1] for x in rows}=={'default','explicit'}
    comparisons+=count
    identity=read(run+'/identity.json');assert identity['backend']=='legacy'
    assert identity['expectedWorkerImage']==candidate['workerImage']
    worker=read(run+'/worker.json')
    assert any(x['imageID']==candidate['workerImage'] and x['ready'] for x in worker['status']['containerStatuses'])

training=0
for run,count in [('candidate-mlp',22),('candidate-lstm',36),('candidate-lstm-repeat',36)]:
    rows=read('regression/'+run+'/comparison.json')
    assert len(rows)==count and all(x['pass_'] for x in rows);training+=count
    pod=read('regression/'+run+'/pod.json')
    env={x['name']:x.get('value') for x in pod['spec']['containers'][0]['env']}
    assert env.get('DISABLE_ADDMM_CUDA_LT')!='1' and env.get('TORCH_CUDNN_V8_API_DISABLED')!='1'
calls=re.findall(r'library api=(\d+) result=(\d+)',(ROOT/'candidate-final-worker.log').read_text())
assert sum(a=='13107' and b=='0' for a,b in calls)==comparisons==198
assert all(b=='0' for a,b in calls)
audit=read('tensor-audit.json');assert audit['status']=='PASS' and audit['tensors']==comparisons+training==292
assert audit['rtol']==1e-4 and audit['atol']==1e-6

lines=(ROOT/'recovery/attestation.log').read_text().splitlines()
proof=json.loads(lines[0]);evidence=proof['evidence']
assert hashlib.sha256(json.dumps(evidence,sort_keys=True).encode()).hexdigest()==proof['evidenceSHA256']
assert len(evidence['scans'])==2
for scan in evidence['scans']:
    assert scan['scannedProcesses']>0 and scan['allocationFiles']
    assert not any(scan[x] for x in ('matches','errors','criSandboxes','criContainers'))
assert json.loads(lines[1])['attested']['phase']=='Detached'
restore=read('restoration.json')
assert restore['status']=='PASS' and restore['VMReady'] and restore['channelPhase']=='Ready'
assert restore['runStrategy']=='Always' and restore['originalVMSpecRestored'] and restore['originalChannelSpecRestored']
assert restore['profileRequestPVCIdentitiesAndSpecsPreserved'] and restore['pluginValuesUnchanged']
assert restore['temporaryNamespacesRemoved'] and restore['temporaryAdminAndObserverRemoved'] and restore['candidateProfileRequestRemoved']
assert restore['protectedControlPlane']=={'vm':True,'vmi':True}
assert read('final-guest-status.json')['activeClient'] is False
assert read('candidate-stream/preflight.json')['podCreated'] is False
print(json.dumps(dict(status='PASS',cnnLegacyForwardComparisons=comparisons,trainingRegressionTensors=training,
                     independentlyAuditedTensors=audit['tensors'],defaultCNNPath='UNSUPPORTED_SIGSEGV',
                     cnnBackward='NOT_TESTED',fullCNNTrainingSupported=False,publishedRuntimeRestored=True),indent=2))
