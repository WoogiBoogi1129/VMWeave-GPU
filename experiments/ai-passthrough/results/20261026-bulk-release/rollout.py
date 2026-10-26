"""Apply verified v0.5.4; preserve VM/PVC identity and old bindings for rollback."""
import json,subprocess,time
from pathlib import Path
D=Path(__file__).resolve().parent;NS='vmweave-test-a';NAME='vmweave-k8s-01';KEY='.local/system-comparison-20261001/artifacts/guest-key'
lock=json.loads((D/'published-lock.json').read_text());images=lock['images']
assert (D/'canary-checked').exists(), 'Published 50%/2GiB canary required'
assert lock['sourceRevision']==(D/'source-revision').read_text().strip()
def run(args,**kw):return subprocess.check_output(list(map(str,args)),text=True,**kw)
def k(*a,**kw):return run(['kubectl',*a],**kw)
def get(kind,name=NAME):return json.loads(k('get',kind,name,'-n',NS,'-o','json'))
def save(name,v): (D/(name+'.json')).write_text(json.dumps(v,indent=2))
def wait(fn,seconds=360):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  v=fn()
  if v:return v
  time.sleep(2)
 raise RuntimeError('Timed out waiting for rollout state; backups retained')
def phase(name):print(name,flush=True);(D/'rollout-phase.txt').write_text(name)
def create(kind,name,spec):
 return json.loads(k('create','-f','-','-o','json',input=json.dumps({'apiVersion':'vmweave.io/v1alpha1','kind':kind,'metadata':{'name':name,'namespace':NS},'spec':spec})))
vm=get('vm');old=json.loads((D/'channel-before.json').read_text())
assert vm['metadata']['uid']==old['spec']['vmRef']['uid']
assert get('sharedmemorychannel')['metadata']['uid']==old['metadata']['uid']
ip=get('vmi')['status']['interfaces'][0]['ipAddress'];ssh=['ssh','-i',KEY,'-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','-o','ConnectTimeout=5','ubuntu@'+ip]
# Refuse a library replacement while another application owns the broker socket.
connections=run(ssh+['sudo ss -xnp']);assert '/run/vmweave/gpu.sock' not in connections,'Active GPU client: do not interrupt'
# Recheck the Worker immediately before mutating production.
worker=get('sharedmemorychannel')['status']['resourcePrefix']+'-worker'
assert '--session ' not in k('exec','-n',NS,worker,'--','ps','-eo','pid,args'), 'Active GPU child'
phase('stage-and-backup')
run(ssh+['mkdir -p /tmp/vmweave-v0.5.4'])
(D/'guest-env-before.txt').write_text(run(ssh+["sudo sh -c 'if test -f /etc/vmweave/guest-broker.env; then cat /etc/vmweave/guest-broker.env; fi'"]))
run(['scp','-i',KEY,'-o','BatchMode=yes','-r',str(D/'published-guest')+'/.',ssh[-1]+':/tmp/vmweave-v0.5.4/'])
(D/'live-guest-before.tgz').touch(mode=0o600,exist_ok=False)
with (D/'live-guest-before.tgz').open('wb') as out:
 subprocess.run(ssh+['sudo tar -czf - /opt/vmweave /etc/systemd/system/vmweave-guest-broker.service'],stdout=out,check=True)
(D/'guest-profile-before.txt').write_text(run(ssh+["sudo sh -c 'if test -f /etc/profile.d/vmweave-bulk-copy.sh; then cat /etc/profile.d/vmweave-bulk-copy.sh; fi'"]))
phase('install-guest-and-halt')
run(ssh+['sudo systemctl stop vmweave-guest-broker.service && sudo sh /tmp/vmweave-v0.5.4/install_guest_broker.sh /tmp/vmweave-v0.5.4 && echo VMWEAVE_BULK_COPY=1 | sudo tee /etc/vmweave/guest-broker.env && echo export VMWEAVE_BULK_COPY=1 | sudo tee /etc/profile.d/vmweave-bulk-copy.sh'])
k('patch','vm',NAME,'-n',NS,'--type=merge','-p',json.dumps({'spec':{'runStrategy':'Halted'}}))
wait(lambda:(c if (c:=get('sharedmemorychannel')).get('status',{}).get('phase')=='Stopped' and not c['status'].get('allocation') else None))
wait(lambda:not k('get','vmi',NAME,'-n',NS,'--ignore-not-found','-o','name').strip())
save('channel-stopped',get('sharedmemorychannel'))
phase('upgrade-operator')
v=json.loads((D/'helm-values.json').read_text());repo,digest=images['operator'].split('@');v['image']={'repository':repo,'digest':digest,'pullPolicy':'IfNotPresent'};save('operator-release-values',v)
print(run(['helm','upgrade','vmweave',D/'vmweave-operator-0.5.4.tgz','-n','vmweave-system','-f',D/'operator-release-values.json','--atomic','--wait','--timeout','300s']),flush=True)
phase('rebind-stopped-channel')
p=json.loads((D/'profile-before.json').read_text())['spec'];p['workerImage']=images['worker'];p=create('GPUProfile','persistent-50-2048-v054',p)
q=json.loads((D/'request-before.json').read_text())['spec'];q['profileRef']={'name':p['metadata']['name'],'uid':p['metadata']['uid']};q=create('GPURequest',NAME+'-v054',q)
k('delete','sharedmemorychannel',NAME,'-n',NS,'--wait=true','--timeout=120s')
annotations=get('vm')['spec']['template']['metadata']['annotations'];clear={n:None for n in annotations if n.startswith('vmweave.io/shm-') or n=='hooks.kubevirt.io/hookSidecars'}
k('patch','vm',NAME,'-n',NS,'--type=merge','-p',json.dumps({'spec':{'template':{'metadata':{'annotations':clear}}}}))
s=old['spec'];s.update({'requestRef':{'name':q['metadata']['name'],'uid':q['metadata']['uid']},'workerImage':images['worker'],'image':images['helper'],'hookImage':images['hook']})
save('channel-recreated',create('SharedMemoryChannel',NAME,s))
k('patch','vm',NAME,'-n',NS,'--type=merge','-p',json.dumps({'spec':{'runStrategy':'Always'}}))
wait(lambda:get('sharedmemorychannel').get('status',{}).get('phase')=='Ready')
assert get('vm')['metadata']['uid']==vm['metadata']['uid'];save('channel-ready',get('sharedmemorychannel'));save('vmi-after',get('vmi'))
phase('rollout-ready');save('rollout-complete',{'status':'PASS','tag':'v0.5.4','sourceRevision':lock['sourceRevision'],'dra_unchanged':True})
