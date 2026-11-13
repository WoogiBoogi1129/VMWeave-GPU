import json,subprocess,pathlib,sys,copy
sys.path.insert(0,'.local/device-plugin-20261105');import lab
R=pathlib.Path('experiments/cnn-training/results/20261113');NS='vmweave-test-b';VM='dp-dev-20261105'
def k(*a):return subprocess.check_output(['kubectl','-n',NS,*a],text=True,timeout=180)
def save(name,o):(R/(name+'.json')).write_text(json.dumps(o,indent=2)+'\n')
assert json.load(open(R/'regression/restored-published-basic/exit.json'))['returncode']==0
for ns in ['cnn-training-20261113','cnn-forward-train-20261113','rnn-default-train-20261113']:
 o=json.loads(lab.ssh('kubectl get ns '+ns+' -o json').stdout);assert o['metadata']['labels']['vmweave-experiment']==ns
 save('cleanup-before-'+ns,o)
 result=lab.ssh('kubectl delete namespace '+ns+' --wait=true --timeout=180s');print(result.stdout,flush=True)
 assert not lab.ssh('kubectl get ns '+ns+' --ignore-not-found -o name').stdout.strip()
admin=json.loads(k('get','pod','cnn-training-build-1113','-o','json'));assert admin['metadata']['labels']['experiment']=='cnn-training-20261113'
save('cleanup-admin',admin);print(k('delete','pod','cnn-training-build-1113','--wait=true','--timeout=60s'),flush=True)
for kind in ['vm','vmi','sharedmemorychannel','gpurequest','gpuprofile','pods','pvc','channelattachments']:
 save('final-'+kind,json.loads(k('get',kind,'-o','json')))
v=json.loads(k('get','vm',VM,'-o','json'));c=json.loads(k('get','sharedmemorychannel',VM,'-o','json'))
old=json.load(open(R/'environment/before-vm.json'))['items'][0]
def normal(spec):
 x=copy.deepcopy(spec);ann=x['template']['metadata']['annotations']
 for key in ['vmweave.io/shm-channel-uid','vmweave.io/shm-allocation','vmweave.io/shm-generation']:ann.pop(key,None)
 for vol in x['template']['spec']['volumes']:
  cloud=vol.get('cloudInitNoCloud')
  if cloud and 'userData' in cloud:cloud['userData']='\n'.join(line for line in cloud['userData'].splitlines() if not line.startswith('# vmweave-layout-b64:'))
 return x
assert v['metadata']['uid']==old['metadata']['uid'] and normal(v['spec'])==normal(old['spec'])
assert v['spec']['runStrategy']=='Always' and c['status']['phase']=='Ready'
assert any(x['type']=='Ready' and x['status']=='True' for x in v['status']['conditions'])
original=json.load(open(R/'baseline-before-channel.json'));assert c['spec']==original['spec']
for kind in ['gpurequest','gpuprofile','pvc']:
 before=json.load(open(R/f'environment/before-{kind}.json'))['items'];after=json.load(open(R/f'final-{kind}.json'))['items']
 assert {o['metadata']['uid']:o['spec'] for o in before}=={o['metadata']['uid']:o['spec'] for o in after},kind
protected={}
for kind in ['vm','vmi']:
 before=json.load(open(R/f'environment/protected-{kind}.json'));after=json.loads(subprocess.check_output(['kubectl','-n','vmweave-nested-k8s','get',kind,'vw-k8s-cp-01','-o','json'],text=True));save('protected-final-'+kind,after)
 assert before['metadata']['uid']==after['metadata']['uid'] and before['spec']==after['spec'];protected[kind]=True
assert json.load(open(R/'baseline-plugin-values.json'))==json.load(open(R/'restored-plugin-values.json'))
guest=json.loads(lab.ssh('sudo cat /run/vmweave-device-plugin/status.json').stdout);save('final-guest-status',guest)
assert guest['ready'] and not guest['activeClient'] and guest['librarySHA256']==json.load(open('deploy/releases/v0.5.9.json'))['guestLibrarySHA256']
save('restoration',dict(status='PASS',runStrategy='Always',VMReady=any(x['type']=='Ready' and x['status']=='True' for x in v['status']['conditions']),channelPhase=c['status']['phase'],originalVMSpecRestored=True,originalChannelSpecRestored=True,profileRequestPVCIdentitiesAndSpecsPreserved=True,pluginValuesUnchanged=True,protectedControlPlane=protected,temporaryNamespacesRemoved=True,temporaryAdminRemoved=True,candidateProfileRequestRemoved=True,publishedGuestSHA256=guest['librarySHA256'],workerImage=c['spec']['workerImage'],normalizedSessionFields=['shm-channel-uid','shm-allocation','shm-generation','vmweave-layout-b64']))
print('PASS normal restoration, idle/reusable public runtime, scoped cleanup and protected VM checks',flush=True)
