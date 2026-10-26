"""Restore the captured v0.5.3 combination if rollout or live checks fail."""
import json,subprocess,time
from pathlib import Path
D=Path(__file__).resolve().parent;NS='vmweave-test-a';NAME='vmweave-k8s-01';KEY='.local/system-comparison-20261001/artifacts/guest-key'
def run(args,**kw):return subprocess.check_output(list(map(str,args)),text=True,**kw)
def k(*a,**kw):return run(['kubectl',*a],**kw)
def get(kind):
 s=k('get',kind,NAME,'-n',NS,'--ignore-not-found','-o','json');return json.loads(s) if s.strip() else None
def wait(fn):
 end=time.monotonic()+360
 while time.monotonic()<end:
  if fn():return
  time.sleep(2)
 raise RuntimeError('Rollback timeout; keep backups and VM/PVC')
old=json.loads((D/'channel-before.json').read_text());vm=json.loads((D/'vm-before.json').read_text());assert get('vm')['metadata']['uid']==vm['metadata']['uid']
vmi=get('vmi');restored=False
if vmi and vmi.get('status',{}).get('interfaces'):
 ip=vmi['status']['interfaces'][0]['ipAddress'];ssh=['ssh','-i',KEY,'-o','BatchMode=yes','-o','ConnectTimeout=5','-o','StrictHostKeyChecking=accept-new','ubuntu@'+ip]
 if subprocess.run(ssh+['true'],capture_output=True).returncode==0:
  run(ssh+['mkdir -p /tmp/vmweave-rollback-v053'])
  run(['scp','-i',KEY,'-o','BatchMode=yes','-r','.local/v053-rollout-20261025/published-guest/.',ssh[-1]+':/tmp/vmweave-rollback-v053/'])
  run(ssh+['sudo systemctl stop vmweave-guest-broker.service; sudo sh /tmp/vmweave-rollback-v053/install_guest_broker.sh /tmp/vmweave-rollback-v053']);restored=True
if restored:
 for file,remote in [('guest-env-before.txt','/etc/vmweave/guest-broker.env'),('guest-profile-before.txt','/etc/profile.d/vmweave-bulk-copy.sh')]:
  text=(D/file).read_text()
  if text:run(ssh+['sudo tee '+remote],input=text)
  else:run(ssh+['sudo rm -f '+remote])
k('patch','vm',NAME,'-n',NS,'--type=merge','-p','{"spec":{"runStrategy":"Halted"}}')
wait(lambda:not get('vmi'))
wait(lambda:not get('sharedmemorychannel') or (get('sharedmemorychannel').get('status',{}).get('phase')=='Stopped' and not get('sharedmemorychannel').get('status',{}).get('allocation')))
h=json.loads(run(['helm','history','vmweave','-n','vmweave-system','-o','json']))
if h[-1]['revision']!=11:run(['helm','rollback','vmweave','11','-n','vmweave-system','--wait','--timeout','300s'])
if get('sharedmemorychannel'):k('delete','sharedmemorychannel',NAME,'-n',NS,'--wait=true','--timeout=120s')
a=get('vm')['spec']['template'].get('metadata',{}).get('annotations',{});clear={n:None for n in a if n.startswith('vmweave.io/shm-') or n=='hooks.kubevirt.io/hookSidecars'}
k('patch','vm',NAME,'-n',NS,'--type=merge','-p',json.dumps({'spec':{'template':{'metadata':{'annotations':clear}}}}))
k('create','-f','-',input=json.dumps({'apiVersion':'vmweave.io/v1alpha1','kind':'SharedMemoryChannel','metadata':{'name':NAME,'namespace':NS},'spec':old['spec']}))
k('patch','vm',NAME,'-n',NS,'--type=merge','-p','{"spec":{"runStrategy":"Always"}}')
wait(lambda:get('sharedmemorychannel').get('status',{}).get('phase')=='Ready')
(D/'rollback-result.json').write_text(json.dumps({'channel_restored':True,'guest_restored_before_boot':restored,'needs_guest_restore_and_reboot':not restored},indent=2));print('Rollback binding Ready; Guest restored:',restored)
