"""Read deployment identities and run bounded, non-destructive GPU/API smoke."""
import json,subprocess,time,hashlib
from pathlib import Path
D=Path(__file__).resolve().parent;NS='vmweave-test-a';NAME='vmweave-k8s-01';KEY='.local/system-comparison-20261001/artifacts/guest-key';lock=json.loads((D/'published-lock.json').read_text())
def k(*a):return subprocess.check_output(['kubectl',*a],text=True)
def get(kind,n=NAME):return json.loads(k('get',kind,n,'-n',NS,'-o','json'))
v=get('vmi');ip=v['status']['interfaces'][0]['ipAddress'];ssh=['ssh','-i',KEY,'-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','-o','ConnectTimeout=5','ubuntu@'+ip]
def remote(cmd):return subprocess.check_output(ssh+[cmd],text=True,timeout=90)
end=time.monotonic()+180
while time.monotonic()<end:
 if subprocess.run(ssh+['systemctl is-active --quiet vmweave-guest-broker.service'],capture_output=True).returncode==0:break
 time.sleep(2)
else:raise RuntimeError('Guest broker not ready')
rev=remote('cat /opt/vmweave/source-revision.txt').strip();assert rev==lock['sourceRevision']
h=remote('sha256sum /opt/vmweave/lib/libvmweave_guest.so').split()[0];assert h==hashlib.sha256((D/'published-guest/libvmweave_guest.so').read_bytes()).hexdigest()
for variant,env in [('default','-u VMWEAVE_STATE_CACHE -u FLYT_STATE_CACHE -u VMWEAVE_BLAS_MATH_CACHE'),('cache','VMWEAVE_STATE_CACHE=1 VMWEAVE_BLAS_MATH_CACHE=1')]:
 s=remote('env '+env+' VMWEAVE_BROKER_SOCKET=/run/vmweave/gpu.sock LD_LIBRARY_PATH=/opt/vmweave/lib /opt/vmweave/bin/guest-gpu-smoke 23 2');assert json.loads(s)['status']=='PASS';(D/('live-gpu-'+variant+'.json')).write_text(s)
subprocess.run(['scp','-i',KEY,'-o','BatchMode=yes',str(Path('.local/math-release-20261022/live_math.py')),ssh[-1]+':/tmp/vmweave-v052-math.py'],check=True)
s=remote('sudo env VMWEAVE_STATE_CACHE=1 VMWEAVE_BLAS_MATH_CACHE=1 VMWEAVE_TEST_NOFAULT=1 VMWEAVE_BROKER_SOCKET=/run/vmweave/gpu.sock LD_LIBRARY_PATH=/opt/vmweave/lib python3 /tmp/vmweave-v052-math.py')
j=json.loads(s);assert j['status']=='PASS' and j['stats'][0]==1 and j['stats'][1]>0;(D/'live-math.json').write_text(s)
remote('rm -f /tmp/vmweave-v052-math.py')
ch=get('sharedmemorychannel');assert ch['status']['phase']=='Ready'
for field,component in [('workerImage','worker'),('image','helper'),('hookImage','hook')]:assert ch['spec'][field]==lock['images'][component]
vm=get('vm');old=json.loads((D/'vm-before.json').read_text());assert vm['metadata']['uid']==old['metadata']['uid'];assert ch['spec']['pvcRef']==json.loads((D/'channel-before.json').read_text())['spec']['pvcRef']
worker=get('pod',ch['status']['resourcePrefix']+'-worker');assert worker['spec']['containers'][0]['image']==lock['images']['worker']
# Compare deployed image references; Ready is not an application SLA proof.
rows=[]
for ns in ['vmweave-system','vmweave-dra-driver',NS]:
 for p in json.loads(k('get','pod','-n',ns,'-o','json'))['items']:
  if ns==NS and not p['metadata']['name'].startswith(ch['status']['resourcePrefix']):continue
  rows.append({'namespace':ns,'name':p['metadata']['name'],'phase':p['status']['phase'],'containers':[{'name':c['name'],'image':c['image']} for c in p['spec']['containers']],'ready':all(c.get('ready',False) for c in p['status'].get('containerStatuses',[])),'imageIDs':[{n:c.get(n) for n in ['name','imageID']} for c in p['status'].get('containerStatuses',[])]})
for namespace,component in [('vmweave-system','operator')]:
 expected=lock['images'][component].split('@')[1]
 assert any(row['namespace']==namespace and row['ready'] and any(c['image'].endswith('@'+expected) for c in row['containers']) for row in rows),component
(D/'running-images.json').write_text(json.dumps(rows,indent=2))
(D/'live-verification.json').write_text(json.dumps({'status':'PASS','sourceRevision':rev,'guestLibrarySHA256':h,'vmUID':vm['metadata']['uid'],'vmiUID':v['metadata']['uid'],'channelUID':ch['metadata']['uid'],'channelPhase':ch['status']['phase'],'pvcRef':ch['spec']['pvcRef'],'scope':'Published Guest/Worker GPU copy/kernel and math-mode API verification; no production fault injection','releaseDefault':'off','productionBulk':'Broker and new login sessions enabled; sudo/service workloads require explicit environment'},indent=2))
print('Published release GPU and math cache smoke PASS',flush=True)
