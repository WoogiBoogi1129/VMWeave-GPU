from common import *
import base64,hashlib,uuid
if any((PRIVATE/role/'disk.img').exists() for role in ('cp','worker')):
    raise SystemExit('Experiment disks already exist; use HANDOFF.md. Refusing changes before installation.')
OUT.mkdir(parents=True,exist_ok=True)
save('inventory/started.txt',datetime.datetime.now(datetime.timezone.utc).isoformat())
save('inventory/source.txt',run(['git','rev-parse','HEAD'],cwd=ROOT)+run(['git','status','--short'],cwd=ROOT))
pods=obj('get','pods','-A')['items']
save('inventory/protected-pods-before.json',[{'namespace':p['metadata']['namespace'],'name':p['metadata']['name'],'uid':p['metadata']['uid'],'status':p.get('status',{})} for p in pods if p['metadata']['namespace'] not in (NS,SYSTEM)])
save('inventory/gpu-before.txt',run(['nvidia-smi','--query-gpu=index,uuid,memory.total,memory.used,utilization.gpu','--format=csv']))
save('inventory/nodes.json',obj('get','nodes'))
save('inventory/protected-channel-before.json',obj('get','sharedmemorychannel','vmweave-k8s-01','-n','vmweave-test-a'))
for ns in (NS,SYSTEM): print(apply({'apiVersion':'v1','kind':'Namespace','metadata':{'name':ns}}))
tls=PRIVATE/'tls';tls.mkdir(exist_ok=True)
run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',tls/'ca.key','-out',tls/'ca.crt','-days','90','-subj','/CN=nested-k8s-experiment-ca'],stderr=subprocess.DEVNULL)
run(['openssl','req','-newkey','rsa:2048','-nodes','-keyout',tls/'tls.key','-out',tls/'tls.csr','-subj',f'/CN=nested-webhook.{SYSTEM}.svc'],stderr=subprocess.DEVNULL)
(tls/'ext').write_text(f'subjectAltName=DNS:nested-webhook.{SYSTEM}.svc,DNS:nested-webhook.{SYSTEM}.svc.cluster.local\n')
run(['openssl','x509','-req','-in',tls/'tls.csr','-CA',tls/'ca.crt','-CAkey',tls/'ca.key','-CAcreateserial','-out',tls/'tls.crt','-days','90','-extfile',tls/'ext'],stderr=subprocess.DEVNULL)
secret=json.loads(k('create','secret','tls','vmweave-webhook-tls','-n',SYSTEM,f'--cert={tls}/tls.crt',f'--key={tls}/tls.key','--dry-run=client','-o','json'));apply(secret)
values={'mode':'active','activeModeAcknowledged':True,'management':{'namespaces':[NS]},'image':{'repository':'ghcr.io/woogiboogi1129/vmweave-operator','digest':'sha256:bcb3e0accc420164bfb09d4c8851fa3c5f09f0f812b90328eb030c955c9356b2'},'tls':{'mode':'existingSecret','existingSecret':'vmweave-webhook-tls','caBundle':base64.b64encode((tls/'ca.crt').read_bytes()).decode()},'nodeSelector':{'kubernetes.io/hostname':'gpu-4'}}
vf=EXP/'manifests/operator-values.json';vf.write_text(json.dumps(values,indent=2))
for registration in ('false','true'):
    output=run(['helm','upgrade','--install','nested',ROOT/'charts/vmweave-operator','--kube-context',CTX,'-n',SYSTEM,'--skip-crds','--wait','--timeout','180s','-f',vf,'--set',f'webhook.registrationEnabled={registration}'])
    save(f'raw/operator-{registration}.txt',output);print(output,flush=True)
items=[]
pub=(PRIVATE/'id_ed25519.pub').read_text().strip()
for role,size,mem,mac in [('cp','40Gi','8Gi','02:00:00:28:10:01'),('worker','80Gi','16Gi','02:00:00:28:10:02'),('shm','1Gi',None,None)]:
    name='nested-'+role;directory=PRIVATE/role;directory.mkdir(exist_ok=True);directory.chmod(0o777)
    if role!='shm':
        disk=directory/'disk.img'
        if disk.exists(): raise RuntimeError('refuse to overwrite existing disk')
        run(['qemu-img','convert','-f','qcow2','-O','raw',ROOT/'.local/k8s-in-vm-20261014/root/disk.qcow2',disk])
        run(['qemu-img','resize',disk,size.replace('Gi','G')]);disk.chmod(0o666)
    items += [{'apiVersion':'v1','kind':'PersistentVolume','metadata':{'name':name},'spec':{'capacity':{'storage':size},'accessModes':['ReadWriteOnce'],'volumeMode':'Filesystem','persistentVolumeReclaimPolicy':'Retain','storageClassName':'','claimRef':{'namespace':NS,'name':name},'local':{'path':str(directory)},'nodeAffinity':{'required':{'nodeSelectorTerms':[{'matchExpressions':[{'key':'kubernetes.io/hostname','operator':'In','values':['gpu-4']}]}]}}}},{'apiVersion':'v1','kind':'PersistentVolumeClaim','metadata':{'name':name,'namespace':NS},'spec':{'accessModes':['ReadWriteOnce'],'volumeMode':'Filesystem','storageClassName':'','volumeName':name,'resources':{'requests':{'storage':size}}}}]
    if role=='shm': continue
    vm='vw-k8s-'+role+'-01'
    user=f'#cloud-config\nhostname: {vm}\nmanage_etc_hosts: true\nusers:\n  - name: ubuntu\n    sudo: ALL=(ALL) NOPASSWD:ALL\n    shell: /bin/bash\n    ssh_authorized_keys:\n      - {pub}\ngrowpart:\n  mode: auto\n  devices: ["/"]\nresize_rootfs: true\n'
    network=f'version: 2\nethernets:\n  eth0:\n    match:\n      macaddress: "{mac}"\n    set-name: eth0\n    dhcp4: true\n'
    items.append({'apiVersion':'kubevirt.io/v1','kind':'VirtualMachine','metadata':{'name':vm,'namespace':NS},'spec':{'runStrategy':'Always','template':{'metadata':{'labels':{'nested-k8s-vm':vm}},'spec':{'nodeSelector':{'kubernetes.io/hostname':'gpu-4'},'domain':{'cpu':{'cores':4},'resources':{'requests':{'cpu':'4','memory':mem}},'machine':{'type':'q35'},'firmware':{'uuid':str(uuid.uuid4())},'devices':{'disks':[{'name':'root','disk':{'bus':'virtio'}},{'name':'cloudinit','disk':{'bus':'virtio'}}],'interfaces':[{'name':'default','masquerade':{},'macAddress':mac}]}},'networks':[{'name':'default','pod':{}}],'volumes':[{'name':'root','persistentVolumeClaim':{'claimName':name}},{'name':'cloudinit','cloudInitNoCloud':{'userData':user,'networkData':network}}]}}}})
    items.append({'apiVersion':'v1','kind':'Service','metadata':{'name':vm,'namespace':NS},'spec':{'selector':{'nested-k8s-vm':vm},'ports':[{'name':'ssh','port':22,'targetPort':22},{'name':'wireguard','port':51820,'targetPort':51820,'protocol':'UDP'}]}})
manifest={'apiVersion':'v1','kind':'List','items':items}
(EXP/'manifests/outer.json').write_text(json.dumps(manifest,indent=2));print(apply(manifest),flush=True)
save('inventory/os-base-sha256.txt',run(['sha256sum',ROOT/'.local/k8s-in-vm-20261014/root/disk.qcow2']))
