from infra import *
import re
image=B/'noble-server-cloudimg-amd64.img'
expected=next(l.split()[0] for l in (B/'ubuntu-SHA256SUMS').read_text().splitlines() if l.endswith('*noble-server-cloudimg-amd64.img'))
assert hashlib.sha256(image.read_bytes()).hexdigest()==expected,'Image download/checksum incomplete'
save(O/'protocol/guest-os.json',{'url':'https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img','sha256':expected,'common_vcpu':4,'common_memory':'16Gi','host_cpu_affinity':[8,9,10,11],'server_cpu_affinity':[12,13,14,15],'memory_numa_policy':'default; observed, not strictly bound'})
for name,ns in [(NAME+'-net',NS),(NAME+'-shm',VNS)]:
 make_vm(name,ns,image)
 s=vm_start(name,ns)
 print(name,'SSH_READY',flush=True)
 remote(s,'sudo cloud-init status --wait',timeout=300)
 print(remote(s,'sudo apt-get update -qq && sudo apt-get install -y -qq libelf1t64 libtirpc3t64 libnghttp2-14 netbase',timeout=600))
 remote(s,'mkdir -p /tmp/comm; sudo mkdir -p /opt/comm; sudo chown ubuntu:ubuntu /opt/comm')
 call(s['scp']+['-r',str(B/'artifacts')+'/','ubuntu@'+s['ip']+':/opt/comm/'])
 remote(s,'ln -sf libtirpc.so.3.0.0 /opt/comm/artifacts/F/libtirpc.so.3; ln -sf cricket-client.so /opt/comm/artifacts/F/libcudart.so.12')
 if ns==VNS:
  remote(s,'sudo sh /opt/comm/artifacts/V/install_guest_broker.sh /opt/comm/artifacts/V')
  # Released installation defaults; no transport tuning.
 print(remote(s,'cat /etc/os-release; uname -r; lspci -nn; ldd /opt/comm/artifacts/L/libcuda.so.1; ldd /opt/comm/artifacts/F/cricket-client.so'))
 vm_stop(name,ns)
 print(name,'PREPARED_AND_HALTED',flush=True)
 if ns==VNS and not get('gpuprofile',name,ns):
  disk(NAME+'-backing',ns)
  create({'apiVersion':'vmweave.io/v1alpha1','kind':'GPUProfile','metadata':{'name':name,'namespace':ns},'spec':{'approved':True,'backend':'hami-dra','draDeviceClass':'vmweave-hami-dra','nodeName':NODE,'gpuUUID':GPU,'cores':100,'memoryMiB':97887,'maxClients':1,'hamiNamespace':'vmweave-dra-driver','schedulerName':'default-scheduler','runtimeClass':'nvidia','workerImage':IM['worker']}})
  print(call(['python3',R/'scripts/operator/create-channel.py','--lifecycle','VM','--namespace',ns,'--vm',name,'--profile',name,'--pvc',NAME+'-backing','--name',name,'--compute','100','--memory','97887Mi','--helper-image',IM['helper'],'--hook-image',IM['hook']]))
  owned=json.loads((B/'owned.json').read_text())
  for kind in ['gpurequest','sharedmemorychannel']:
   x=get(kind,name,ns);owned.append({'kind':kind,'namespace':ns,'name':name,'uid':x['metadata']['uid']})
  save(B/'owned.json',owned)
  wait(lambda:get('sharedmemorychannel',name,ns).get('status',{}).get('phase')=='Stopped')
print('VMS_PREPARED',flush=True)
