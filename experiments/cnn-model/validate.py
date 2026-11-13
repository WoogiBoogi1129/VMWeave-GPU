#!/usr/bin/env python3
"""Validate archived CNN composition, raw-audit evidence and lab restoration."""
import hashlib
import json
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parent/'results/20261113'
def read(name):return json.loads((ROOT/name).read_text())
manifest=read('artifacts.json')['sha256']
assert set(manifest)=={str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file() and p.name not in ('artifacts.json','validation.json')}
for name,digest in manifest.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
identity=read('candidate-artifact-identity.json')
for name,digest in identity['sourceSHA256'].items():
    assert hashlib.sha256((ROOT/'runtime-source'/name).read_bytes()).hexdigest()==digest,name
workload=read('workload-identity.json')
for name,digest in workload['sourceSHA256'].items():
    assert hashlib.sha256((ROOT/'source'/name).read_bytes()).hexdigest()==digest,name
official='docker.io/pytorch/pytorch@sha256:eee11b3b3872a8c838e35ef48f08b2d5def2080902c7f666831310ca1a0ef2be'
cases=[('relu',70,10,10),('pool',70,10,10),('cnn',300,20,40),('cnn-repeat',300,20,40),('mnist',300,20,40)]
previous={a:0 for a in ('13107','13111','13115')};total=steps=0
for name,count,nsteps,native in cases:
    run='candidate-'+name;rows=read(run+'/comparison.json')
    assert len(rows)==count and all(x['passed'] for x in rows)
    assert {x['step'] for x in rows}=={1,2,3,4,5}
    configs={'d1'} if name in ('relu','pool') else {'d0','d1'}
    assert {x['key'] for x in rows}=={k+'/'+s for k in configs for s in ('default','explicit')}
    pod=read(run+'/pod.json');status=read(run+'/exit.json')
    assert pod['status']['phase']=='Succeeded' and status['returncode']==0 and not status['timeout']
    app=next(x for x in pod['spec']['containers'] if x['name']=='pytorch')
    actual=next(x for x in pod['status']['containerStatuses'] if x['name']=='pytorch')
    assert app['image']==actual['imageID']==official
    assert identity['guestLibrarySHA256'] in ' '.join(pod['spec']['initContainers'][0]['args'])
    runid=read(run+'/identity.json');assert runid['backend']=='legacy'
    assert runid['guestLibrarySHA256']==identity['guestLibrarySHA256'] and runid['expectedWorkerImage']==identity['workerImage']
    code=read(run+'/code.json')['data']
    assert hashlib.sha256(code['mnist.b64'].encode()).hexdigest()==workload['fixtureSHA256']
    for f,s in code.items():assert hashlib.sha256(s.encode()).hexdigest()==runid['sourceSHA256'][f]
    worker=read(run+'/worker.json');digest=identity['workerImage'].split('@')[1]
    names={x['name'] for x in worker['spec']['containers'] if x['image']==identity['workerImage']}
    assert any(x['name'] in names and x['ready'] and x['imageID'].rsplit('@',1)[-1]==digest for x in worker['status']['containerStatuses'])
    calls=re.findall(r'library api=(\d+) result=(\d+)',(ROOT/(run+'-worker.log')).read_text())
    assert calls and all(rc=='0' for _,rc in calls)
    current={api:sum(a==api for a,_ in calls) for api in previous}
    assert all(current[a]-previous[a]==native for a in previous),run
    previous=current;total+=count;steps+=nsteps
assert total==1040 and steps==80 and set(previous.values())=={140}
audit=read('tensor-audit.json');assert audit['status']=='PASS' and audit['tensors']==1040
assert audit['rtol']==1e-4 and audit['atol']==1e-6
for name in ('candidate-basic-after','restored-published-basic'):
    p=read('regression/'+name+'/pod.json');s=read('regression/'+name+'/exit.json')
    assert p['status']['phase']=='Succeeded' and s['returncode']==0 and not s['timeout']
restore=read('restoration.json')
assert restore['status']=='PASS' and restore['VMReady'] and restore['runStrategy']=='Always' and restore['channelPhase']=='Ready'
for key in ('originalVMSpecRestored','originalChannelSpecRestored','profileRequestPVCIdentitiesAndSpecsPreserved',
            'pluginValuesUnchanged','temporaryNamespacesRemoved','noTemporaryAdminCreated','candidateProfileRequestRemoved'):
    assert restore[key],key
assert restore['protectedControlPlane']=={'vm':True,'vmi':True}
assert read('final-guest-status.json')['activeClient'] is False
assert restore['publishedGuestSHA256'] in ' '.join(read('regression/restored-published-basic/pod.json')['spec']['initContainers'][0]['args'])
print(json.dumps(dict(status='PASS',gpuSteps=steps,comparedTensors=total,independentlyAuditedTensors=audit['tensors'],
                     convolutionForward=140,convolutionBackwardData=140,convolutionBackwardFilter=140,
                     publishedRuntimeRestored=True,runtimeChanges=False,scope='small legacy FP32 CNN correctness; no throughput/accuracy claim'),indent=2))
