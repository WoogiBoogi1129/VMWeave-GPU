from common import *
vmname='vw-k8s-worker-01'
if k('get','sharedmemorychannel',vmname,'-n',NS,'--ignore-not-found','-o','name').strip():
    raise SystemExit('GPU Channel already exists; use the documented lifecycle recovery procedure.')
print(k('patch','vm',vmname,'-n',NS,'--type=merge','-p','{"spec":{"runStrategy":"Halted"}}'),flush=True)
print(k('wait','--for=delete','vmi/'+vmname,'-n',NS,'--timeout=180s'),flush=True)
old=obj('get','gpuprofile','persistent-50-2048-v055','-n','vmweave-test-a')
profile={'apiVersion':'vmweave.io/v1alpha1','kind':'GPUProfile','metadata':{'name':'nested-50-2048','namespace':NS},'spec':old['spec']}
print(apply(profile),flush=True)
def ref(o):return {x:o['metadata'][x] for x in ('name','uid')}
vm=obj('get','vm',vmname,'-n',NS);p=obj('get','gpuprofile','nested-50-2048','-n',NS);pvc=obj('get','pvc','nested-shm','-n',NS)
q={'apiVersion':'vmweave.io/v1alpha1','kind':'GPURequest','metadata':{'name':vmname,'namespace':NS},'spec':{'vmRef':ref(vm),'profileRef':ref(p),'count':1,'compute':50,'memory':'2048Mi'}}
print(apply(q),flush=True);q=obj('get','gpurequest',vmname,'-n',NS)
baseline=obj('get','sharedmemorychannel','vmweave-k8s-01','-n','vmweave-test-a')['spec']
c={'apiVersion':'vmweave.io/v1alpha1','kind':'SharedMemoryChannel','metadata':{'name':vmname,'namespace':NS},'spec':{'vmRef':ref(vm),'requestRef':ref(q),'pvcRef':ref(pvc),'lifecycle':'VM','sessions':1,'uid':107,'gid':107,**{x:baseline[x] for x in ('image','workerImage','hookImage')}}}
(EXP/'manifests/gpu.json').write_text(json.dumps({'apiVersion':'v1','kind':'List','items':[profile,q,c]},indent=2))
print(apply(c),flush=True)
print(k('patch','vm',vmname,'-n',NS,'--type=merge','-p','{"spec":{"runStrategy":"Always"}}'),flush=True)
for _ in range(120):
    status=obj('get','sharedmemorychannel',vmname,'-n',NS).get('status',{})
    if status.get('phase')=='Ready':break
    time.sleep(3)
else:save('raw/channel-not-ready.json',status);raise RuntimeError('channel not ready')
save('inventory/initial-channel.json',obj('get','sharedmemorychannel',vmname,'-n',NS))
for _ in range(60):
    try:
        ssh('worker','sudo systemctl is-active --quiet vmweave-guest-broker && test -S /run/vmweave/gpu.sock',stderr=subprocess.DEVNULL);break
    except subprocess.CalledProcessError:time.sleep(3)
else:raise RuntimeError('broker not ready')
save('gpu/guest-smoke.log',ssh('worker','env LD_LIBRARY_PATH=/opt/vmweave/lib VMWEAVE_BROKER_SOCKET=/run/vmweave/gpu.sock /opt/vmweave/bin/guest-gpu-smoke',stderr=subprocess.STDOUT))
save('gpu/guest-broker-initial.log',ssh('worker','sudo journalctl -u vmweave-guest-broker --no-pager; getent group vmweave'))
print('GUEST GPU SMOKE COMPLETE',flush=True)
