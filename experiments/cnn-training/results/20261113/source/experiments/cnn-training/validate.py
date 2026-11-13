#!/usr/bin/env python3
"""Audit archived runs, paired binaries, actual SHM calls and restoration."""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent/'results/20261113'
def read(name):return json.loads((ROOT/name).read_text())
manifest=read('artifacts.json')
assert set(manifest['sha256'])=={str(p.relative_to(ROOT)) for p in ROOT.rglob('*')
                               if p.is_file() and p.name not in ('artifacts.json','validation.json')}
for name,digest in manifest['sha256'].items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
identity=read('candidate-artifact-identity.json')
for name,digest in identity['sourceSHA256'].items():
    assert hashlib.sha256((ROOT/'source'/name).read_bytes()).hexdigest()==digest,name
image='docker.io/pytorch/pytorch@sha256:eee11b3b3872a8c838e35ef48f08b2d5def2080902c7f666831310ca1a0ef2be'
training=[('candidate-input-v2',30,6,0),('candidate-weight',36,0,6),
          ('candidate-minimal',42,6,6),('candidate-matrix',576,96,96),
          ('candidate-matrix-repeat',576,96,96),('candidate-accumulate',42,12,12)]
regression=['regression/'+s for s in ('candidate-forward','candidate-mlp','candidate-lstm',
                                     'candidate-lstm-repeat','candidate-basic-after','restored-published-basic')]
success=[x[0] for x in training]+regression
for name in success+['forward-only-baseline-retry','candidate-input']:
    pod=read(name+'/pod.json');status=read(name+'/exit.json')
    app=next(x for x in pod['spec']['containers'] if x['name']=='pytorch')
    actual=next(x for x in pod['status']['containerStatuses'] if x['name']=='pytorch')
    assert app['image']==actual['imageID']==image,name
    assert not status['timeout']
    if name in success:
        assert status['returncode']==0 and pod['status']['phase']=='Succeeded',name
    else:
        assert status['returncode']==(-11 if name=='forward-only-baseline-retry' else 1)
        assert pod['status']['phase']=='Failed'
    if 'candidate-' in name:
        assert identity['guestLibrarySHA256'] in ' '.join(pod['spec']['initContainers'][0]['args'])
    env={x['name']:x.get('value') for x in app['env']}
    assert env.get('DISABLE_ADDMM_CUDA_LT')!='1'
    if name.startswith('regression/') and name!='regression/candidate-forward':
        assert env.get('TORCH_CUDNN_V8_API_DISABLED')!='1'

def calls(name):
    rows=re.findall(r'library api=(\d+) result=(\d+)',(ROOT/name).read_text())
    assert rows and all(rc=='0' for _,rc in rows),name
    return {api:sum(a==api for a,_ in rows) for api in ('13107','13111','13115')}
previous=calls('candidate-input-worker.log')
assert previous=={'13107':1,'13111':1,'13115':0}
tensors=0;forward=data=weight=0
for name,count,dc,wc in training:
    rows=read(name+'/comparison.json')
    assert len(rows)==count and all(x['passed'] for x in rows),name
    assert {x['key'].split('/')[1] for x in rows}=={'default','explicit'}
    assert {x['step'] for x in rows}=={1,2,3}
    entry=read(name+'/identity.json');assert entry['backend']=='legacy'
    assert entry['expectedWorkerImage']==identity['workerImage']
    assert entry['guestLibrarySHA256']==identity['guestLibrarySHA256']
    worker=read(name+'/worker.json')
    digest=identity['workerImage'].rsplit('@',1)[1]
    names={x['name'] for x in worker['spec']['containers'] if x['image']==identity['workerImage']}
    assert any(x['name'] in names and x['ready'] and x['imageID'].rsplit('@',1)[-1]==digest
               for x in worker['status']['containerStatuses'])
    current=calls(name+'-worker.log');fc=max(dc,wc)
    assert {a:current[a]-previous[a] for a in current}=={'13107':fc,'13111':dc,'13115':wc},name
    previous=current;tensors+=count;forward+=fc;data+=dc;weight+=wc
assert tensors==1302 and forward==222 and data==weight==216
rows=read('regression/candidate-forward/comparison.json')
assert len(rows)==96 and all(x['passed'] for x in rows)
for name,count in [('candidate-mlp',22),('candidate-lstm',36),('candidate-lstm-repeat',36)]:
    rows=read('regression/'+name+'/comparison.json')
    assert len(rows)==count and all(x['pass_'] for x in rows)
final=calls('candidate-final-worker.log')
assert final=={'13107':319,'13111':217,'13115':216}
audit=read('tensor-audit.json')
assert audit['status']=='PASS' and audit['tensors']==1492 and audit['rtol']==1e-4 and audit['atol']==1e-6
restore=read('restoration.json')
assert restore['status']=='PASS' and restore['VMReady'] and restore['channelPhase']=='Ready'
assert restore['runStrategy']=='Always'
for key in ('originalVMSpecRestored','originalChannelSpecRestored','profileRequestPVCIdentitiesAndSpecsPreserved',
            'pluginValuesUnchanged','temporaryNamespacesRemoved','temporaryAdminRemoved','candidateProfileRequestRemoved'):
    assert restore[key],key
assert restore['protectedControlPlane']=={'vm':True,'vmi':True}
assert read('final-guest-status.json')['activeClient'] is False
assert restore['publishedGuestSHA256'] in ' '.join(read('regression/restored-published-basic/pod.json')['spec']['initContainers'][0]['args'])
print(json.dumps(dict(status='PASS',cnnTrainingTensors=tensors,gpuTrainingSteps=216,
                     successfulBackwardDataCalls=data,successfulBackwardFilterCalls=weight,
                     independentAuditTensors=audit['tensors'],publishedRuntimeRestored=True,
                     scope='explicit legacy FP32 Conv2d; not full CNN/model/performance support'),indent=2))
