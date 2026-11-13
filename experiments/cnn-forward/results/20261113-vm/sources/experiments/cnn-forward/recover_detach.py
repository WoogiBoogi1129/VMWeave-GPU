"""One-shot, evidence-based recovery for the pinned Nov 13 test VM.

Run in a hostPID diagnostic Pod on the affected node, using the controller's
service account. Default is read-only; --attest records actual observed detach.
Never removes finalizers, deletes memory files, or changes admission policy.
"""
import argparse
import datetime as dt
import errno
import hashlib
import json
import os
from pathlib import Path
import ssl
import subprocess
import time
import urllib.request

def epoch(value):
    return dt.datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()

def validate(c, vm, vmi, pod, channel, att, node, boot_id, boot_time):
    assert vm['metadata']['uid']==c['vmUID'] and vm['spec']['runStrategy']=='Halted'
    assert vmi['metadata']['uid']==c['vmiUID'] and vmi['status']['phase']=='Failed'
    assert vmi['status']['nodeName']==c['node']
    assert pod['metadata']['uid']==c['podUID'] and pod['metadata'].get('deletionTimestamp')
    assert pod['metadata']['labels']['kubevirt.io/created-by']==c['vmiUID']
    assert pod['spec']['nodeName']==c['node'] and pod['status']['phase']=='Failed'
    assert channel['metadata']['uid']==c['channelUID'] and channel['status']['phase']=='Draining'
    assert channel['status']['generation']==c['generation'] and channel['status']['allocation']==c['allocation']
    assert channel['status']['vmiUID']==c['vmiUID'] and channel['status']['nodeName']==c['node']
    assert att['spec']['channelRef']['uid']==c['channelUID'] and att['spec']['holderUID']==c['vmiUID']
    assert att['spec']['generation']==c['generation'] and att['spec']['role']=='guest' and att['spec']['nodeName']==c['node']
    assert att['status']['phase']=='Mapped' and att['status']['launcherPodUID']==c['podUID']
    assert node['status']['nodeInfo']['bootID']==boot_id
    assert any(x['type']=='Ready' and x['status']=='True' for x in node['status']['conditions'])
    # Positive reboot evidence, not merely absent Pod/VMI evidence.
    assert epoch(c['archivedRunningAt']) < boot_time < epoch(pod['metadata']['deletionTimestamp'])
    assert epoch(pod['status']['startTime']) < boot_time
    sandbox=next(x for x in pod['status']['conditions'] if x['type']=='PodReadyToStartContainers')
    assert sandbox['status']=='False' and sandbox['reason']=='PodSandboxNotReady'
    assert epoch(sandbox['lastTransitionTime'])>=boot_time
    for statuses in ('containerStatuses','initContainerStatuses','ephemeralContainerStatuses'):
        for s in pod['status'].get(statuses,[]):
            assert not s.get('ready') and 'running' not in s['state']

def scan(c):
    directory=Path('/host'+c['shmPath'])/c['allocation']
    files={}
    for p in directory.rglob('*'):
        if p.is_file():
            s=p.stat();files[(s.st_dev,s.st_ino)]=str(p.relative_to(directory))
    assert files, 'no allocation files to positively identify'
    matches=[]; errors=[]; scanned=0
    for p in Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name)==os.getpid():continue
        try:
            cmd=(p/'cmdline').read_bytes()
            if any(v.encode() in cmd for v in (c['vmiUID'],c['podUID'],c['allocation'])):
                matches.append(dict(pid=int(p.name),kind='process-identity'))
            for line in (p/'maps').read_text().splitlines():
                fields=line.split(maxsplit=5);maj,minr=fields[3].split(':')
                key=(os.makedev(int(maj,16),int(minr,16)),int(fields[4]))
                if key in files:matches.append(dict(pid=int(p.name),kind='mapping',file=files[key]))
            for fd in (p/'fd').iterdir():
                try:s=fd.stat()
                except FileNotFoundError:continue
                if (s.st_dev,s.st_ino) in files:matches.append(dict(pid=int(p.name),kind='fd',file=files[(s.st_dev,s.st_ino)]))
            scanned+=1
        except (FileNotFoundError,ProcessLookupError):continue
        except OSError as e:
            if e.errno not in (errno.ENOENT,errno.ESRCH):errors.append(dict(pid=int(p.name),errno=e.errno))
    def cri(verb,key):
        args=['chroot','/host','crictl','--runtime-endpoint','unix:///var/run/crio/crio.sock',verb]
        if verb=='ps':args+=['-a']
        args+=['-o','json']
        result=json.loads(subprocess.check_output(args,text=True,timeout=30))
        return [x['id'] for x in result.get(key,[]) if x.get('labels',{}).get('io.kubernetes.pod.uid')==c['podUID']]
    proof=dict(scannedProcesses=scanned,allocationFiles=sorted(files.values()),matches=matches,errors=errors,
               criSandboxes=cri('pods','items'),criContainers=cri('ps','containers'))
    assert scanned>0 and not matches and not errors and not proof['criSandboxes'] and not proof['criContainers'],proof
    return proof

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attest',action='store_true');a=parser.parse_args()
    c=json.loads(Path('/evidence/config.json').read_text())
    assert c['namespace']=='vmweave-test-b' and c['name']=='dp-dev-20261105'
    ca='/var/run/secrets/kubernetes.io/serviceaccount/'
    def api(path,method='GET',body=None):
        token=Path(ca+'token').read_text().strip()
        req=urllib.request.Request('https://kubernetes.default.svc'+path,method=method,
             data=None if body is None else json.dumps(body).encode(),
             headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with urllib.request.urlopen(req,context=ssl.create_default_context(cafile=ca+'ca.crt'),timeout=20) as r:return json.load(r)
    core='/api/v1/namespaces/'+c['namespace']+'/'
    kv='/apis/kubevirt.io/v1/namespaces/'+c['namespace']+'/'
    vw='/apis/vmweave.io/v1alpha1/namespaces/'+c['namespace']+'/'
    def observe():
        objects=[api(kv+'virtualmachines/'+c['name']),api(kv+'virtualmachineinstances/'+c['name']),
                 api(core+'pods/'+c['pod']),api(vw+'sharedmemorychannels/'+c['name']),
                 api(vw+'channelattachments/'+c['name']+'-guest'),api('/api/v1/nodes/'+c['node'])]
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        boot_time=int(next(x.split()[1] for x in Path('/proc/stat').read_text().splitlines() if x.startswith('btime ')))
        validate(c,*objects,boot_id,boot_time)
        return objects,boot_id,boot_time
    _,boot_id,boot_time=observe()
    proofs=[scan(c)];time.sleep(1);proofs.append(scan(c))
    objects,final_boot,final_time=observe();assert (boot_id,boot_time)==(final_boot,final_time)
    evidence=dict(nodeBootID=boot_id,nodeBootTimeUTC=dt.datetime.fromtimestamp(boot_time,dt.timezone.utc).isoformat(),
                  archivedRunningAt=c['archivedRunningAt'],config=c,scans=proofs,observedAt=dt.datetime.now(dt.timezone.utc).isoformat())
    digest=hashlib.sha256(json.dumps(evidence,sort_keys=True).encode()).hexdigest()
    print(json.dumps(dict(evidence=evidence,evidenceSHA256=digest)),flush=True)
    if a.attest:
        att=objects[4]
        att['status']=dict(phase='Detached',observedGeneration=att['metadata']['generation'],
                          launcherPodUID=c['podUID'],evidence='VerifiedNodeRebootNoMappings:'+boot_id+':'+digest)
        updated=api(vw+'channelattachments/'+c['name']+'-guest/status','PUT',att)
        print(json.dumps(dict(attested=updated['status'],attachmentUID=updated['metadata']['uid'])),flush=True)
    else:print('READ_ONLY_VERIFIED',flush=True)

if __name__=='__main__':main()
