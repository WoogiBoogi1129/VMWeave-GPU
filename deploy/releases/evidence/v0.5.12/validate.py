#!/usr/bin/env python3
"""Check archived release identities, GPU correctness, rollout and preservation."""
import hashlib,json
from pathlib import Path
E=Path(__file__).resolve().parent;R=E.parents[3]
def read(name):return json.loads((E/name).read_text())
manifest=read('artifacts.json')['sha256']
actual={str(p.relative_to(E)) for p in E.rglob('*') if p.is_file() and p.name not in ('artifacts.json','validation-check.json')}
assert set(manifest)==actual
for name,digest in manifest.items():assert hashlib.sha256((E/name).read_bytes()).hexdigest()==digest,name
release=json.loads((R/'deploy/releases/v0.5.12.json').read_text());plugin=json.loads((R/'deploy/releases/device-plugin-v0.1.4.json').read_text())
assert release==read('release-record.json') and plugin==read('plugin-record.json')
assert release['sourceRevision']==plugin['sourceRevision']=='2cd0fe428f2ee2b99fa43777b2967854904966ac'
assert release['chart']['version']=='0.5.12' and plugin['chart']['version']=='0.1.4'
assert release['guestLibrarySHA256']==plugin['guestLibrarySHA256']==read('guest-package-equivalence.json')['librarySHA256']
for name,ref in release['images'].items():assert read('published-images.json')[name]==dict(reference=ref,sourceRevision=release['sourceRevision'])
v=read('validation.json');assert v['status']=='PASS' and v['testNamespacesRemoved'] and v['sessionsReclaimed']
assert not v['batchDefaultEnabled'] and not v['performanceMeasurement']
b=read('batch/validation.json');assert b['status']=='PASS' and len(b['cases'])==4
assert b['librarySHA256']==release['guestLibrarySHA256'] and b['workerImage']==release['images']['worker']
assert [c['mode'] for c in b['cases']]==['normal','normal','error','normal']
for c in b['cases']:
    assert c['returncode']==0 and c['brokerIdle']
    assert 'PASS:' in (E/'batch'/(c['name']+'.stdout.txt')).read_text()
    if c['batchEnabled']:assert 'kernel-batch v1 enabled' in (E/'batch'/(c['name']+'.stderr.txt')).read_text()
total=0
for name,count in [('relu',70),('pool',70),('cnn',300),('cnn-repeat',300),('mnist',300),('mlp',22),('lstm',36),('basic',0)]:
    group='training' if name in ('mlp','lstm','basic') else 'cnn';path=group+'/published-'+name
    pod=read(path+'/pod.json');status=read(path+'/exit.json')
    assert pod['status']['phase']=='Succeeded' and status['returncode']==0 and not status['timeout']
    assert pod['spec']['initContainers'][0]['image']==plugin['images']['guest']['runtimeReference']
    if count:
        rows=read(path+'/comparison.json');assert len(rows)==count and all(x.get('passed',x.get('pass_')) for x in rows);total+=count
assert total==1098 and read('cnn/tensor-audit.json')['status']=='PASS'
assert read('published-idle/pod.json')['status']['phase']=='Succeeded' and read('published-idle/stdout.txt')['status']=='PASS'
assert read('gpu-observation.json')['status']=='PASS'
p=read('preservation.json');assert p['status']=='PASS' and p['adminPodRemoved'] and p['hamiValuesUnchanged'] and p['otherHelmReleasesUnchanged']
assert all(x['specUnchanged'] for x in p['preExistingUnresolvedChannels'])
assert read('broker-final.json')['ready'] and not read('broker-final.json')['activeClient']
assert read('sharedmemorychannel-after.json')['status']['phase']=='Ready' and read('vmi-after.json')['status']['phase']=='Running'
assert {x['chartVersion'] for x in read('helm-releases.json')}=={'0.5.12','0.1.4'}
for d in read('deployments-after.json'):
    assert d['ready'] and d['image']==release['images']['operator']
    assert d['imageID'].rsplit('@',1)[-1]==release['images']['operator'].split('@')[1]
print(json.dumps(dict(status='PASS',runtime='v0.5.12',plugin='0.1.4',tensorComparisons=total,batchCases=4,protectedRunningPods=p['protectedRunningPods']),indent=2))
