import json,pathlib,sys,time,yaml
sys.path.insert(0,'.local/device-plugin-20261105');import lab
D=pathlib.Path('.local/cnn-release-20261113');E=pathlib.Path('deploy/releases/evidence/v0.5.10');R=E/'published-idle-host';R.mkdir()
assert json.loads((E/'validation.json').read_text())['status']=='PASS'
ns='cnn-release-idle-20261113';manifest=dict(apiVersion='v1',kind='Namespace',metadata=dict(name=ns,labels={'vmweave-experiment':ns}))
# Send JSON over stdin to the established SSH command without shell interpolation.
import subprocess,shlex
def k(*args,data=None):
 return subprocess.check_output(lab.ssh_args()+[shlex.join(['kubectl',*args])],input=data,text=True,timeout=180)
pods=json.loads(k('get','pods','-A','-o','json'))['items'];assert not [p for p in pods if p['status']['phase'] not in ['Succeeded','Failed'] and any(c.get('resources',{}).get('limits',{}).get('vmweave.io/gpu') for c in p['spec']['containers'])]
k('create','-f','-',data=json.dumps(manifest))
for _ in range(60):
 if k('-n',ns,'get','sa','default','--ignore-not-found','-o','name').strip():break
 time.sleep(1)
else:raise TimeoutError('serviceaccount')
p=yaml.safe_load(pathlib.Path('integrations/kubernetes-device-plugin/workloads/pod.yaml').read_text());p['metadata']=dict(name='published-idle-host',namespace=ns,labels={'vmweave-experiment':ns});p['spec']['activeDeadlineSeconds']=120;p['spec']['nodeSelector']={'kubernetes.io/hostname':lab.VM}
app=p['spec']['containers'][0];app['image']=json.loads((D/'plugin-image-identities.json').read_text())['-workload']['reference'];app['command']=['/opt/vmweave/bin/sgemm'];app['args']=['30']
(R/'submitted.json').write_text(json.dumps(p,indent=2)+'\n');k('create','-f','-',data=json.dumps(p))
for _ in range(90):
 pod=json.loads(k('-n',ns,'get','pod','published-idle-host','-o','json'))
 if pod['status']['phase'] in ['Succeeded','Failed']:break
 time.sleep(2)
(R/'pod.json').write_text(json.dumps(pod,indent=2)+'\n');logs=k('-n',ns,'logs','published-idle-host');(R/'stdout.txt').write_text(logs)
assert pod['status']['phase']=='Succeeded' and json.loads(logs)['status']=='PASS'
k('delete','namespace',ns,'--wait=true','--timeout=120s')
assert not k('get','ns',ns,'--ignore-not-found','-o','name').strip()
print('Published workload SGEMM/idle PASS and namespace removed')
