import pathlib,json,subprocess,sys,copy,re,hashlib,shutil,time
D=pathlib.Path('.local/cnn-release-20261113');E=pathlib.Path('deploy/releases/evidence/v0.5.10');ROOT=pathlib.Path('.')
sys.path.insert(0,'.local/device-plugin-20261105');import lab
NS=lab.NS;VM=lab.VM
read=lambda p:json.loads(p.read_text())
def save(p,o):p.write_text(json.dumps(o,indent=2)+'\n')
def k(*a):return subprocess.check_output(['kubectl',*a],text=True,timeout=180)
validation=read(E/'validation.json');assert validation['status']=='PASS'
rollout=read(D/'rollout-result.json');source=rollout['sourceRevision'];images=rollout['images'];dp=D/'device-plugin'
proof=read(E/'gpu-observation.json');assert proof['status']=='PASS'
assert any('NSpid:' in s and int(s.split('NSpid:')[1].split()[-1]) in {x['pid'] for x in proof['sessions']} for s in proof['hostProcessStatus'].values())
protected=[];pending=[]
for old in read(D/'sharedmemorychannels-before.json')['items']:
 m=old['metadata']
 if (m['namespace'],m['name'])==(NS,VM):continue
 now=json.loads(k('-n',m['namespace'],'get','sharedmemorychannel',m['name'],'-o','json'))
 assert now['metadata']['uid']==m['uid'] and now['spec']==old['spec']
 pending.append(dict(namespace=m['namespace'],name=m['name'],uid=m['uid'],beforePhase=old['status']['phase'],afterPhase=now['status']['phase'],reason=now['status'].get('reason'),specUnchanged=True))
for old in read(D/'vmi-before.json')['items']:
 m=old['metadata']
 if (m['namespace'],m['name'])==(NS,VM) or old['status']['phase']!='Running':continue
 now=json.loads(k('-n',m['namespace'],'get','vmi',m['name'],'-o','json'));assert now['metadata']['uid']==m['uid'] and now['spec']==old['spec'] and now['status']['phase']=='Running'
 protected.append(dict(namespace=m['namespace'],name=m['name'],uid=m['uid'],specUnchanged=True,phase='Running'))
for kind in ['vm','vmi','sharedmemorychannel']:
 now=json.loads(k('-n',NS,'get',kind,VM,'-o','json'));save(E/(kind+'-after.json'),now)
v=read(E/'vm-after.json');c=read(E/'sharedmemorychannel-after.json')
oldv=next(o for o in read(D/'vm-before.json')['items'] if (o['metadata']['namespace'],o['metadata']['name'])==(NS,VM))
def normalized(spec):
 s=copy.deepcopy(spec);ann=s['template']['metadata']['annotations']
 for n in ['vmweave.io/shm-channel-uid','vmweave.io/shm-allocation','vmweave.io/shm-generation','hooks.kubevirt.io/hookSidecars']:ann.pop(n,None)
 for vol in s['template']['spec']['volumes']:
  cloud=vol.get('cloudInitNoCloud')
  if cloud and 'userData' in cloud:cloud['userData']='\n'.join(x for x in cloud['userData'].splitlines() if not x.startswith('# vmweave-layout-b64:'))
 return s
assert v['metadata']['uid']==oldv['metadata']['uid'] and normalized(v['spec'])==normalized(oldv['spec'])
assert v['spec']['runStrategy']=='Always' and any(x['type']=='Ready' and x['status']=='True' for x in v['status']['conditions'])
assert read(E/'vmi-after.json')['status']['phase']=='Running' and c['status']['phase']=='Ready'
assert c['spec']==read(D/'created-channel.json')['spec'] and c['spec']['workerImage']==images['worker']
for kind,original in [('gpuprofile','gpuprofiles-before'),('gpurequest','gpurequests-before'),('pvc','pvc-before')]:
 after=json.loads(k('get',kind,'-A','-o','json'))['items'];byuid={o['metadata']['uid']:o for o in after}
 for old in read(D/(original+'.json'))['items']:assert old['metadata']['uid'] in byuid and old['spec']==byuid[old['metadata']['uid']]['spec'],(kind,old['metadata']['name'])
for kind in ['gpuprofile','gpurequest']:save(E/(kind+'-after.json'),json.loads(k('-n',NS,'get',kind,VM+'-v0510','-o','json')))
assert read(E/'gpuprofile-after.json')['spec']['workerImage']==images['worker']
state=json.loads(lab.ssh('sudo cat /run/vmweave-device-plugin/status.json').stdout);assert state['ready'] and not state['activeClient'] and state['librarySHA256']==rollout['guestLibrarySHA256'];save(E/'broker-final.json',state)
helm=[]
for name,ns,prefix in [('nested','vmweave-nested-system','nested'),('vmweave','vmweave-system','vmweave')]:
 values=json.loads(subprocess.check_output(['helm','get','values',name,'-n',ns,'-o','json']));assert values==read(D/(prefix+'-values-after.json'))
 before=read(D/(prefix+'-values-before.json'));expected=copy.deepcopy(before);expected['image']['digest']=images['operator'].split('@')[1];assert values==expected
 status=json.loads(subprocess.check_output(['helm','status',name,'-n',ns,'-o','json']));assert status['info']['status']=='deployed'
 helm.append(dict(name=name,namespace=ns,revision=status['version'],status='deployed',chartVersion='0.5.10'))
plugin_status=json.loads(lab.ssh('helm status vmweave-device-plugin -n vmweave-device-plugin -o json').stdout);assert plugin_status['info']['status']=='deployed'
assert json.loads(lab.ssh('helm get values vmweave-device-plugin -n vmweave-device-plugin -o json').stdout)==read(D/'plugin-values-after.json')
helm.append(dict(name='vmweave-device-plugin',namespace='vmweave-device-plugin',revision=plugin_status['version'],status='deployed',chartVersion='0.1.2'))
admin=json.loads(k('-n',NS,'get','pod','v0510-release-admin','-o','json'));assert admin['metadata']['uid']==read(D/'admin-created.json')['metadata']['uid'] and admin['metadata']['labels']['task']=='v0510-release-20261113'
k('-n',NS,'delete','pod','v0510-release-admin','--wait=true','--timeout=60s');assert not k('-n',NS,'get','pod','v0510-release-admin','--ignore-not-found','-o','name').strip()
save(E/'preservation.json',dict(status='PASS',protectedRunningVMs=protected,preExistingUnresolvedChannels=pending,adminPodRemoved=True,previousProfileRequestPVCIdentitiesAndSpecsPreserved=True,vmSpecPreservedExceptSessionBindingAndHookImage=True,helmValuesPreservedExceptPublishedImageAndGuestHash=True,externalComponentsNotUpgraded=['Kubernetes','KubeVirt','HAMi device plugin','HAMi DRA driver','GPU Operator']))
for name in ['deployments-after.json','plugin-pods-after.json','plugin-values-after.json','plugin-image-identities.json','guest-node-after.json','broker-after-install.json','worker-pod-after.json','worker-binaries.txt','guest-install.txt','plugin-upgrade.txt','operator-chart-pull.txt','plugin-chart-pull.txt','nested-upgrade.txt','vmweave-upgrade.txt','created-profile.json','created-request.json','created-channel.json','replaced-channel.json','guest-package-equivalence.json','rollout-control.log','rollout.log','verify_live.log','observe-live.log','observe-host.log','idle-probe.log','idle-probe-host.log','runtime-release.json','docs-build-final.log','deployment-tests.log','library-tests.log']:
 shutil.copyfile(D/name,E/name)
save(E/'helm-releases.json',helm);save(E/'published-images.json',{name:dict(reference=ref,sourceRevision=source) for name,ref in images.items()})
def chart(name,version,path,log):return dict(reference='oci://ghcr.io/woogiboogi1129/charts/'+name,version=version,digest=re.search(r'Digest: (sha256:[0-9a-f]{64})',log.read_text()).group(1),packageSHA256=hashlib.sha256(path.read_bytes()).hexdigest())
record=dict(tag='v0.5.10',sourceRevision=source,publishedDateKST='2026-11-13',releaseURL=read(D/'runtime-release.json')['html_url'],activeProfile=NS+'/'+VM+'-v0510',activeRequest=NS+'/'+VM+'-v0510',previousProfileAndRequestRetainedForRollback=True,scope='Paired legacy FP32 Conv2d forward/backward and small CNN correctness; central Helm and test VM runtime upgraded.',chart=chart('vmweave-operator','0.5.10',D/'vmweave-operator-0.5.10.tgz',D/'operator-chart-pull.txt'),images=images,helmReleases=helm,deployments=read(D/'deployments-after.json'),devicePluginRecord='deploy/releases/device-plugin-v0.1.2.json',validation='deploy/releases/evidence/v0.5.10/validation.json',evidence='deploy/releases/evidence/v0.5.10/README.md',guestLibrarySHA256=rollout['guestLibrarySHA256'],protectedRunningVMs=protected,preExistingUnresolvedChannels=pending,externalComponentsNotUpgraded=['Kubernetes','KubeVirt','HAMi device plugin','HAMi DRA driver','GPU Operator'],limits=['CNN requires TORCH_CUDNN_V8_API_DISABLED=1, FP32 contiguous NCHW, groups=1, dilation=1, benchmark=False.','Small CNN and MNIST 80-example correctness; no full-dataset accuracy/convergence or throughput claim.','Default cuDNN graph, BatchNorm, AMP, ResNet/YOLO and arbitrary GPU operations not validated.','Pre-existing Draining channels retained without forced cleanup.','Clean-cluster installation remains NOT_RUN.'])
save(pathlib.Path('deploy/releases/v0.5.10.json'),record);save(pathlib.Path('deploy/releases/v0.5.10-values.json'),dict(image=dict(repository='ghcr.io/woogiboogi1129/vmweave-operator',digest=images['operator'].split('@')[1])))
release=read(dp/'release.json');identities=read(D/'plugin-image-identities.json');published=read(dp/'images.json');plugin_images={}
for suffix,key in [('', 'plugin'),('-guest','guest'),('-workload','workload')]:
 tag='ghcr.io/woogiboogi1129/vmweave-device-plugin'+suffix+':device-plugin-v0.1.2';m=next(x for x in published if tag in x['RepoTags']);plugin_images[key]=dict(reference=m['RepoDigests'][0],imageID=m['Id'],runtimeReference=identities[suffix]['reference'])
plugin=dict(component='VMWeave guest Kubernetes device plugin',version='0.1.2',tag='device-plugin-v0.1.2',sourceRevision=source,releaseURL=release['html_url'],workflow='https://github.com/WoogiBoogi1129/VMWeave-GPU/actions/runs/43394472501',guestLibrarySHA256=rollout['guestLibrarySHA256'],images=plugin_images,chart=chart('vmweave-device-plugin','0.1.2',dp/'vmweave-device-plugin-0.1.2.tgz',D/'plugin-chart-pull.txt'),assets={a['name']:dict(url=a['browser_download_url'],sha256=hashlib.sha256((dp/a['name']).read_bytes()).hexdigest()) for a in release['assets']},validation=record['validation'],operatorCompatibility='v0.5.10 paired Guest/Worker required for legacy CNN; scheduling contract unchanged',scope=dict(resource='vmweave.io/gpu',slotsPerVM=1,concurrentCUDAClients=1,guestKubernetes='1.35.9',guestCRI='CRI-O 1.35.10',workloads=['Legacy FP32 Conv/ReLU/MaxPool/Linear CNN, synthetic and MNIST subset','FP32 MLP default cuBLASLt','FP32 LSTM default cuDNN','Basic CUDA matmul']))
save(pathlib.Path('deploy/releases/device-plugin-v0.1.2.json'),plugin);save(pathlib.Path('deploy/releases/current.json'),dict(tag=record['tag'],record='deploy/releases/v0.5.10.json',guide='docs/getting-started/release-v0.5.10.md'))
print('RELEASE RECORDS AND PRESERVATION PASS',flush=True)
