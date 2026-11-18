import profiles
from infra import *
import hashlib
image=B/'noble-server-cloudimg-amd64.img'
expected=next(l.split()[0] for l in (B/'ubuntu-SHA256SUMS').read_text().splitlines() if l.endswith('*'+image.name))
assert hashlib.sha256(image.read_bytes()).hexdigest()==expected
save(O/'protocol/guest-os.json',{'sha256':expected,'url':'https://cloud-images.ubuntu.com/noble/current/'+image.name,'cpu':4,'memory':'16Gi'})
name=NAME+'-shm';ns=VNS
make_vm(name,ns,image)
s=vm_start(name,ns)
try:
 print('VM_BOOTED',flush=True)
 remote(s,'sudo cloud-init status --wait',timeout=300)
 remote(s,'sudo apt-get update -qq && sudo apt-get install -y -qq libelf1t64 libtirpc3t64 netbase',timeout=600)
 remote(s,'sudo mkdir -p /opt/comm/artifacts /tmp/comm; sudo chown -R ubuntu:ubuntu /opt/comm')
 call(s['scp']+['-r',str(B/'artifacts/V'),'ubuntu@'+s['ip']+':/opt/comm/artifacts/'])
 copy(s,[B/'artifacts/sequence.ptx',B/'artifacts/sequence.cubin'],'/opt/comm/artifacts/')
 print(remote(s,'sudo sh /opt/comm/artifacts/V/install_guest_broker.sh /opt/comm/artifacts/V'),flush=True)
 (O/'evidence/guest-prepared.txt').write_text(remote(s,'cat /etc/os-release; uname -r; cat /etc/vmweave/guest-broker.env; sha256sum /opt/comm/artifacts/V/probe /opt/vmweave/lib/libvmweave_guest.so'))
 profiles.prepare_next(s)
finally:vm_stop(name,ns)
if not get('gpuprofile',name,ns):
 disk(NAME+'-backing',ns)
 create({'apiVersion':'vmweave.io/v1alpha1','kind':'GPUProfile','metadata':{'name':name,'namespace':ns},'spec':{'approved':True,'backend':'hami-dra','draDeviceClass':'vmweave-hami-dra','nodeName':NODE,'gpuUUID':GPU,'cores':100,'memoryMiB':97887,'maxClients':1,'hamiNamespace':'vmweave-dra-driver','schedulerName':'default-scheduler','runtimeClass':'nvidia','workerImage':IM['worker']}})
 print(call(['python3',R/'scripts/operator/create-channel.py','--lifecycle','VM','--namespace',ns,'--vm',name,'--profile',name,'--pvc',NAME+'-backing','--name',name,'--compute','100','--memory','97887Mi','--helper-image',IM['helper'],'--hook-image',IM['hook']]))
 owned=json.loads((B/'owned.json').read_text())
 for kind in ['gpurequest','sharedmemorychannel']:
  x=get(kind,name,ns);owned.append({'kind':kind,'namespace':ns,'name':name,'uid':x['metadata']['uid']})
 save(B/'owned.json',owned)
 wait(lambda:get('sharedmemorychannel',name,ns).get('status',{}).get('phase')=='Stopped')
save(O/'evidence/setup-complete.json',{'utc':time.time(),'vm':name,'gpu':GPU,'halted':True})
print('SETUP_COMPLETE',flush=True)
