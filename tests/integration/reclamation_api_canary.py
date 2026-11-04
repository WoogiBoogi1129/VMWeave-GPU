#!/usr/bin/env python3
"""Opt-in real-API/filesystem canary; synthetic detach, no GPU/VM boot.

Requires kubectl admin access and a local path visible on --node. Creates only
uniquely named test resources. Evidence remains in --output. No production CRs
are changed. The tested manager must support the additive reclamation schema.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
from datetime import datetime, timezone

REPO = Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--manager',required=True);p.add_argument('--image',required=True)
    p.add_argument('--node',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--namespace',default='vmweave-reclamation-canary')
    args=p.parse_args();ns=args.namespace
    assert ns.startswith('vmweave-reclamation-canary'), 'test-only namespace required'
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    root=out/'backing';root.mkdir(exist_ok=True)
    def k(*argv,body=None):
        r=subprocess.run(['kubectl',*argv],input=None if body is None else json.dumps(body),text=True,capture_output=True,timeout=60)
        if r.returncode:raise RuntimeError(r.stderr)
        return r.stdout
    def create(o):return json.loads(k('create','-f','-','-o','json',body=o))
    def get(kind,name):
        raw=k('get',kind,name,'-n',ns,'--ignore-not-found','-o','json');return json.loads(raw) if raw.strip() else None
    def patchstatus(kind,name,status):return json.loads(k('patch',kind,name,'-n',ns,'--subresource=status','--type=merge','-p',json.dumps({'status':status}),'-o','json'))
    def save(name,value):(out/name).write_text(json.dumps(value,indent=2)+'\n')
    def wait(fn,seconds=150):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            value=fn()
            if value:return value
            time.sleep(1)
        raise TimeoutError('canary convergence')
    def owner(c):return [{'apiVersion':c['apiVersion'],'kind':c['kind'],'name':c['metadata']['name'],'uid':c['metadata']['uid'],'controller':True,'blockOwnerDeletion':True}]
    assert get('namespace',ns) is None,'test namespace already exists'
    create({'apiVersion':'v1','kind':'Namespace','metadata':{'name':ns}})
    pvname=ns+'-'+uuid.uuid4().hex[:8]
    create({'apiVersion':'v1','kind':'PersistentVolume','metadata':{'name':pvname},'spec':{'capacity':{'storage':'1Gi'},'accessModes':['ReadWriteOnce'],'persistentVolumeReclaimPolicy':'Retain','storageClassName':'','local':{'path':str(root)},'nodeAffinity':{'required':{'nodeSelectorTerms':[{'matchExpressions':[{'key':'kubernetes.io/hostname','operator':'In','values':[args.node]}]}]}}}})
    pvc=create({'apiVersion':'v1','kind':'PersistentVolumeClaim','metadata':{'name':'backing','namespace':ns},'spec':{'volumeName':pvname,'storageClassName':'','accessModes':['ReadWriteOnce'],'resources':{'requests':{'storage':'1Gi'}}}})
    script=(REPO/'operator/internal/engine/reclaim_helper.py').read_text()
    fixtures={};results=[];proc=None
    # Real API journals and real helper Pods. Detach statuses are synthetic:
    # there is no VMI, Worker, CUDA mapping, or GPU allocation to reclaim.
    for name,point,mode in [('normal',None,'Allocation'),('partial','unlinked_channel','Allocation'),('removed','removed_directory','Allocation'),('completed','complete','Allocation'),('persistent','unlinked_layout.bin','VM')]:
        allocation,generation=uuid.uuid4().hex,uuid.uuid4().hex
        target=root/allocation;target.mkdir(mode=0o750)
        (target/'channel').write_bytes(b'canary backing');(target/'layout.bin').write_bytes(b'canary layout')
        (target/'ready.json').write_text(json.dumps({'allocationId':allocation,'generation':generation}))
        vm=create({'apiVersion':'kubevirt.io/v1','kind':'VirtualMachine','metadata':{'name':name,'namespace':ns},'spec':{'runStrategy':'Halted','template':{'spec':{'domain':{'devices':{},'resources':{'requests':{'memory':'64Mi'}}}}}}})
        spec={'lifecycle':mode,'vmRef':{'name':name,'uid':vm['metadata']['uid']},'requestRef':{'name':name,'uid':str(uuid.uuid4())},'pvcRef':{'name':'backing','uid':pvc['metadata']['uid']},'image':args.image,'workerImage':args.image,'hookImage':args.image,'sessions':1,'uid':os.getuid(),'gid':os.getgid()}
        c=create({'apiVersion':'vmweave.io/v1alpha1','kind':'SharedMemoryChannel','metadata':{'name':name,'namespace':ns,'finalizers':['vmweave.io/shm-detach']},'spec':spec})
        st={'phase':'Draining','allocation':allocation,'generation':generation,'vmiUID':str(uuid.uuid4()),'workerPodUID':str(uuid.uuid4()),'nodeName':args.node,'everBound':True}
        evidence={}
        for role in ['guest','worker']:
            at=create({'apiVersion':'vmweave.io/v1alpha1','kind':'ChannelAttachment','metadata':{'name':name+'-'+role,'namespace':ns,'ownerReferences':owner(c)},'spec':{'channelRef':{'name':name,'uid':c['metadata']['uid']},'generation':generation,'holderUID':st['vmiUID' if role=='guest' else 'workerPodUID'],'role':role,'nodeName':args.node}})
            at=patchstatus('channelattachment',at['metadata']['name'],{'phase':'Detached','observedGeneration':at['metadata']['generation']})
            evidence[role]={'uid':at['metadata']['uid'],'generation':at['metadata']['generation'],'spec':at['spec'],'status':at['status']}
        if point:
            identity={'channelUID':c['metadata']['uid'],'vmUID':vm['metadata']['uid'],'pvcUID':pvc['metadata']['uid'],**{key:st.get(key,'') for key in ['allocation','generation','vmiUID','workerPodUID','backend','claimUID','claimName']}}
            authorization=json.dumps({'identity':identity,'detachEvidence':evidence,'authorizedAt':datetime.now(timezone.utc).isoformat()},sort_keys=True,separators=(',',':'))
            cm=create({'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':name+'-recovery','namespace':ns,'ownerReferences':owner(c)},'data':{'authorization':authorization,'progress':'{"phase":"Authorized"}'}})
            st['reclamation']={'journalName':cm['metadata']['name'],'journalUID':cm['metadata']['uid'],'authorization':authorization}
            recover=name+'-recover'
            create({'apiVersion':'v1','kind':'ServiceAccount','metadata':{'name':recover,'namespace':ns,'ownerReferences':owner(c)}})
            create({'apiVersion':'rbac.authorization.k8s.io/v1','kind':'Role','metadata':{'name':recover,'namespace':ns,'ownerReferences':owner(c)},'rules':[{'apiGroups':[''],'resources':['configmaps'],'resourceNames':[cm['metadata']['name']],'verbs':['get','update']}]})
            create({'apiVersion':'rbac.authorization.k8s.io/v1','kind':'RoleBinding','metadata':{'name':recover,'namespace':ns,'ownerReferences':owner(c)},'roleRef':{'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':recover},'subjects':[{'kind':'ServiceAccount','name':recover,'namespace':ns}]})
        c=patchstatus('sharedmemorychannel',name,st);assert c['status']==st or c['status'].get('reclamation')==st.get('reclamation')
        if point:
            faultscript=script.split("if __name__ == '__main__':")[0]+'''\ndef checkpoint(point):
    if point == sys.argv[6]:
        os._exit(99)
root, namespace, name, uid, authorization, point = sys.argv[1:]
reclaim(root, json.loads(authorization)['identity'], APIJournal(namespace,name,uid,authorization), checkpoint)
'''
            command=['python3','-c',faultscript,'/flyt-channel',ns,cm['metadata']['name'],cm['metadata']['uid'],authorization,point]
            podname=name+'-fault'
            create({'apiVersion':'v1','kind':'Pod','metadata':{'name':podname,'namespace':ns,'ownerReferences':owner(c)},'spec':{'nodeSelector':{'kubernetes.io/hostname':args.node},'serviceAccountName':recover,'restartPolicy':'Never','securityContext':{'runAsUser':os.getuid(),'runAsGroup':os.getgid(),'fsGroup':os.getgid()},'containers':[{'name':'main','image':args.image,'command':command,'volumeMounts':[{'name':'channel','mountPath':'/flyt-channel'}]}],'volumes':[{'name':'channel','persistentVolumeClaim':{'claimName':'backing'}}]}})
            pod=wait(lambda:(x if (x:=get('pod',podname)) and x.get('status',{}).get('phase') in ['Succeeded','Failed'] else None))
            save(name+'-fault-pod.json',pod)
            assert pod['status']['containerStatuses'][0]['state']['terminated']['exitCode']==99, k('logs',podname,'-n',ns)
            journal=get('configmap',cm['metadata']['name']);save(name+'-interrupted-journal.json',journal)
            k('delete','pod',podname,'-n',ns,'--wait=true','--timeout=60s')
        fixtures[name]={'channel':c,'vm':vm,'target':str(target),'mode':mode,'fault':point}
    save('fixtures.json',fixtures)
    log=(out/'controller.log').open('w')
    proc=subprocess.Popen([str(Path(args.manager).resolve()),'--component=controller','--mode=active','--namespaces='+ns,'--system-namespace='+ns+'-system','--leader-elect=false','--health-bind-address=127.0.0.1:18141','--metrics-bind-address=127.0.0.1:18142'],stdout=log,stderr=log)
    try:
        for name,f in fixtures.items():
            def done():
                assert proc.poll() is None,'controller exited'
                c=get('sharedmemorychannel',name)
                return c is None if f['mode']=='Allocation' else c and c['status']['phase']=='Stopped'
            wait(done)
            assert not Path(f['target']).exists(),name+' backing retained'
            assert get('configmap',name+'-recovery') is None,name+' journal retained'
            for kind in ['pod','role','rolebinding','serviceaccount']:assert get(kind,name+'-recover') is None,(name,kind)
            vm=get('vm',name);assert vm['metadata']['uid']==f['vm']['metadata']['uid'] and vm['spec']==f['vm']['spec'],'VM changed'
            if f['mode']=='VM':
                c=get('sharedmemorychannel',name);assert not c['status'].get('reclamation') and not c['status'].get('completion') and not c['status'].get('allocation')
            results.append({'case':name,'crashAfter':f['fault'],'lifecycle':f['mode'],'backingRemoved':True,'journalAndCredentialsRemoved':True,'vmUnchanged':True})
            print('PASS',name,flush=True)
        assert not json.loads(k('get','vmi','-n',ns,'-o','json'))['items']
        save('result.json',{'status':'PASS','scope':'Real Kubernetes API, filesystem, least-privilege helper Pods and controller. Synthetic detach evidence; no real GPU mapping or VM boot. Node reboot/storage loss not tested.','manager':str(Path(args.manager).resolve()),'cases':results})
    finally:
        proc.terminate();proc.wait(timeout=20);log.close()
    # Cleanup only after all assertions pass. Failures retain isolated evidence.
    for name,f in fixtures.items():
        c=get('sharedmemorychannel',name)
        if c:
            assert c['status']['phase']=='Stopped' and not c['status'].get('allocation')
            k('patch','sharedmemorychannel',name,'-n',ns,'--type=json','-p',json.dumps([{'op':'test','path':'/metadata/uid','value':c['metadata']['uid']},{'op':'replace','path':'/metadata/finalizers','value':[]}]))
    k('delete','namespace',ns,'--wait=true','--timeout=90s')
    k('delete','pv',pvname,'--wait=true','--timeout=60s')
    assert not list(root.iterdir());root.rmdir()
    print('CANARY_PASS_AND_CLEANED',flush=True)

if __name__=='__main__':main()
