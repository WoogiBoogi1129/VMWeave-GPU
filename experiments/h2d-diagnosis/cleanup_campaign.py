"""Remove completed campaign objects with API-level UID deletion preconditions."""
from common import *
import urllib.request,urllib.error
assert (OUT/'followup-complete.json').exists()
assert GPU not in call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
runs={p.name for p in (OUT/'runs').iterdir() if p.is_dir()}
# Every candidate must have been observed in this campaign's actual create response.
created=set()
for line in (OUT/'commands.jsonl').read_text().splitlines():
    row=json.loads(line)
    if row.get('exit_code')!=0 or 'create' not in row.get('command',[]):continue
    try:o=json.loads(row['stdout'])
    except (ValueError,KeyError):continue
    if isinstance(o,dict) and 'metadata' in o:created.add((o.get('kind'),o['metadata'].get('name'),o['metadata'].get('uid')))
# script create-channel output is not always JSON: channel-bound and Released snapshots are authoritative.
for p in (OUT/'runs').glob('*/channel-*.json'):
    o=json.loads(p.read_text());created.add((o['kind'],o['metadata']['name'],o['metadata']['uid']))
    ref=o['spec']['requestRef'];created.add(('GPURequest',ref['name'],ref['uid']))
resources=[('vm','VirtualMachine','/apis/kubevirt.io/v1/namespaces/vmweave-performance-tcp/virtualmachines'),('vm','VirtualMachine','/apis/kubevirt.io/v1/namespaces/'+NS+'/virtualmachines'),
 ('gpurequests.vmweave.io','GPURequest','/apis/vmweave.io/v1alpha1/namespaces/'+NS+'/gpurequests'),
 ('sharedmemorychannels.vmweave.io','SharedMemoryChannel','/apis/vmweave.io/v1alpha1/namespaces/'+NS+'/sharedmemorychannels'),
 ('gpuprofiles.vmweave.io','GPUProfile','/apis/vmweave.io/v1alpha1/namespaces/'+NS+'/gpuprofiles'),
 ('pvc','PersistentVolumeClaim','/api/v1/namespaces/'+NS+'/persistentvolumeclaims'),
 ('pv','PersistentVolume','/api/v1/persistentvolumes')]
# Release channel finalizers while their VM/request references still exist.
resources.sort(key=lambda r:0 if r[1]=='SharedMemoryChannel' else 1)
plan=[]
for resource,kind,path in resources:
    namespace='vmweave-performance-tcp' if '/vmweave-performance-tcp/' in path else NS
    items=json.loads(k('get',resource,'-n',namespace,'-o','json'))['items']
    for o in items:
        n=o['metadata']['name'];uid=o['metadata']['uid']
        if n not in runs and not (kind=='GPUProfile' and n.startswith('scprofile-') and n[10:] in runs):continue
        if (kind,n,uid) not in created and kind=='GPURequest':
            ref=o['spec']['vmRef'];assert ('VirtualMachine',ref['name'],ref['uid']) in created and ref['name']==n
            created.add((kind,n,uid))
        assert (kind,n,uid) in created,('No recorded creation evidence',kind,n,uid)
        if kind=='SharedMemoryChannel':assert o['status']['phase']=='Released'
        if kind=='VirtualMachine':assert not get('vmi',n,ns=namespace),'Still running VM'
        plan.append({'kind':kind,'name':n,'uid':uid,'api_path':path+'/'+n,'snapshot':o})
save(OUT/'cleanup-plan.json',plan)
proxylog=(BASE/'cleanup-proxy.txt').open('w')
proxy=subprocess.Popen(['kubectl','proxy','--address=127.0.0.1','--port=18081'],stdout=proxylog,stderr=subprocess.STDOUT)
try:
    def ready():
        assert proxy.poll() is None, 'Campaign proxy failed to start'
        try:return urllib.request.urlopen('http://127.0.0.1:18081/version',timeout=2).status==200
        except OSError:return False
    wait(ready,30)
    results=[]
    for item in plan:
        body={'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':item['uid']},'propagationPolicy':'Background'}
        request=urllib.request.Request('http://127.0.0.1:18081'+item['api_path'],data=json.dumps(body).encode(),headers={'Content-Type':'application/json'},method='DELETE')
        try:
            with urllib.request.urlopen(request,timeout=30) as response:result=json.load(response)
        except urllib.error.HTTPError as e:
            if e.code!=404:raise
            result={'already_garbage_collected':True}
        results.append({k:item[k] for k in ['kind','name','uid']}|{'result':result})
        if item['kind']=='SharedMemoryChannel':
            def channel_gone():
                current=get('sharedmemorychannels.vmweave.io',item['name'])
                if current:assert current['metadata']['uid']==item['uid']
                return current is None
            wait(channel_gone,120)
    save(OUT/'cleanup-deletions.json',results)
finally:proxy.terminate();proxy.wait();proxylog.close()
# Remove only the retained stopped image references recorded for this campaign.
retained=json.loads((BASE/'retained-images.json').read_text());removed=[]
for r in retained:
    cid=r['container_id'];raw=admin(['chroot','/host','podman','inspect',cid],check=False)
    if not raw.strip():continue
    objects=json.loads(raw)
    if not objects:
        removed.append({'id':cid,'name':r['name'],'already_absent':True});continue
    obj=objects[0];assert obj['Id']==cid and not obj['State']['Running']
    removed.append({'id':cid,'name':r['name'],'output':admin(['chroot','/host','podman','rm',cid])})
save(OUT/'cleanup-retained-containers.json',removed)
