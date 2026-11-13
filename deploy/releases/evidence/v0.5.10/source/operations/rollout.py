import pathlib,json,subprocess,time,sys,shlex,hashlib
D=pathlib.Path('.local/cnn-release-20261113');E=pathlib.Path('deploy/releases/evidence/v0.5.10')
sys.path.insert(0,'.local/device-plugin-20261105');import lab
NS=lab.NS;VM=lab.VM;source=(D/'source-revision.txt').read_text().strip();images=json.loads((D/'images.json').read_text());release=D/'device-plugin'
def run(argv,**kw):return subprocess.check_output(argv,text=True,timeout=900,**kw)
def k(*a):return run(['kubectl','-n',NS,*a])
def save(n,o):(D/(n+'.json')).write_text(json.dumps(o,indent=2)+'\n')
def get(kind,name=VM):
 s=k('get',kind,name,'--ignore-not-found','-o','json');return json.loads(s) if s.strip() else None
def wait(f,seconds=300):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  try:
   value=f()
   if value:return value
  except (subprocess.CalledProcessError,json.JSONDecodeError):pass
  time.sleep(2)
 raise TimeoutError('release runtime transition')
def host(*a):return k('exec','v0510-release-admin','--','chroot','/host',*a)
def patchvm(ops):
 v=get('vm');return k('patch','vm',VM,'--type=json','-p',json.dumps([dict(op='test',path='/metadata/uid',value=v['metadata']['uid']),dict(op='test',path='/metadata/resourceVersion',value=v['metadata']['resourceVersion'])]+ops))
def create(o):return json.loads(run(['kubectl','create','-f','-','-o','json'],input=json.dumps(o)))
assert get('sharedmemorychannel')['status']['phase']=='Ready' and get('vm')['spec']['runStrategy']=='Always'
# Immutable public artifacts are verified before any Guest files change.
for component in ['worker','helper','hook']:
 (D/(component+'-node-pull.txt')).write_text(host('crictl','--runtime-endpoint','unix:///var/run/crio/crio.sock','pull',images[component]))
 meta=json.loads(host('podman','image','inspect',images[component]))[0];assert meta['Labels']['org.opencontainers.image.revision']==source;save(component+'-node-image',meta)
 print('Verified host image',component,flush=True)
for line in (release/'SHA256SUMS').read_text().splitlines():
 sha,name=line.split();assert pathlib.Path(name).name==name and hashlib.sha256((release/name).read_bytes()).hexdigest()==sha
lab.copy(release/'images.docker.tar.gz','/home/ubuntu/v0510-plugin-images.tar.gz');lab.copy(release/'vmweave-device-plugin-0.1.2.tgz','/home/ubuntu/v0510-plugin-chart.tgz')
result=lab.ssh('sudo podman load -i /home/ubuntu/v0510-plugin-images.tar.gz');(D/'guest-image-load.txt').write_text(result.stdout+result.stderr)
published=json.loads((release/'images.json').read_text());identities={};refs={}
for suffix in ['','-guest','-workload']:
 tag='ghcr.io/woogiboogi1129/vmweave-device-plugin'+suffix+':device-plugin-v0.1.2';meta=json.loads(lab.ssh('sudo podman image inspect '+shlex.quote(tag)).stdout)[0];original=next(m for m in published if tag in m['RepoTags'])
 assert meta['Id'].removeprefix('sha256:')==original['Id'].removeprefix('sha256:')
 assert meta['Labels']['org.opencontainers.image.revision']==source
 refs[suffix]=meta['RepoDigests'][0];identities[suffix]=dict(reference=refs[suffix],imageID=meta['Id'],publishedRepoDigests=original['RepoDigests'])
save('plugin-image-identities',identities)
lab.ssh('sudo mkdir -p /home/ubuntu/v0510-guest; cid=$(sudo podman create '+shlex.quote(refs['-guest'])+'); sudo podman cp "$cid":/opt/vmweave/guest/. /home/ubuntu/v0510-guest/; sudo podman rm "$cid"')
verified=lab.ssh('cd /home/ubuntu/v0510-guest && sha256sum -c SHA256SUMS && cat source-revision.txt');(D/'guest-checksums.txt').write_text(verified.stdout)
sha=lab.ssh('sha256sum /home/ubuntu/v0510-guest/libvmweave_guest.so').stdout.split()[0];assert sha in (release/'guest-identity.txt').read_text() and source in verified.stdout
assert (D/'published-runtime-guest/source-revision.txt').read_text().strip()==source
assert hashlib.sha256((D/'published-runtime-guest/libvmweave_guest.so').read_bytes()).hexdigest()==sha
save('guest-package-equivalence',dict(runtimeGuestImage=images['guest-artifacts'],devicePluginGuestImage=refs['-guest'],librarySHA256=sha,sourceRevision=source,match=True))
pods=json.loads(lab.ssh('kubectl get pods -A -o json').stdout)['items'];assert not [p for p in pods if p['status']['phase'] not in ['Succeeded','Failed'] and any(c.get('resources',{}).get('limits',{}).get('vmweave.io/gpu') for c in p['spec']['containers'])]
state=json.loads(lab.ssh('sudo cat /run/vmweave-device-plugin/status.json').stdout);assert state['ready'] and not state['activeClient'];save('broker-before-install',state)
lab.ssh('sudo tar -czf /home/ubuntu/v0510-guest-backup.tar.gz /opt/vmweave/lib /opt/vmweave/control /opt/vmweave/source-revision.txt /etc/vmweave /etc/systemd/system/vmweave-guest-broker.service')
result=lab.ssh('sudo systemctl stop vmweave-guest-broker && sudo sh /home/ubuntu/v0510-guest/install_guest_broker.sh /home/ubuntu/v0510-guest');(D/'guest-install.txt').write_text(result.stdout+result.stderr)
assert lab.ssh('sha256sum /opt/vmweave/lib/libvmweave_guest.so').stdout.split()[0]==sha
patchvm([dict(op='replace',path='/spec/runStrategy',value='Halted')])
wait(lambda:not get('vmi') and get('sharedmemorychannel')['status']['phase']=='Stopped')
old=get('sharedmemorychannel');save('replaced-channel',old)
q=get('gpurequest',old['spec']['requestRef']['name']);p=get('gpuprofile',q['spec']['profileRef']['name'])
p={key:p[key] for key in ['apiVersion','kind','spec']};p['metadata']=dict(name=VM+'-v0510',namespace=NS);p['spec']['workerImage']=images['worker'];p=create(p);save('created-profile',p)
q={key:q[key] for key in ['apiVersion','kind','spec']};q['metadata']=dict(name=VM+'-v0510',namespace=NS);q['spec']['profileRef']={key:p['metadata'][key] for key in ['name','uid']};q=create(q);save('created-request',q)
assert get('sharedmemorychannel')['metadata']['uid']==old['metadata']['uid'];k('delete','sharedmemorychannel',VM,'--wait=true','--timeout=180s')
c={key:old[key] for key in ['apiVersion','kind','spec']};c['metadata']=dict(name=VM,namespace=NS);c['spec'].update(workerImage=images['worker'],image=images['helper'],hookImage=images['hook'],requestRef={key:q['metadata'][key] for key in ['name','uid']});c=create(c);save('created-channel',c)
v=get('vm');assert v['spec']['runStrategy']=='Halted' and not get('vmi') and v['spec']['template']['metadata']['annotations']['vmweave.io/shm-channel-uid']==old['metadata']['uid']
keys=['vmweave.io/shm-channel','vmweave.io/shm-channel-uid','vmweave.io/shm-allocation','vmweave.io/shm-generation','hooks.kubevirt.io/hookSidecars']
patchvm([dict(op='remove',path='/spec/template/metadata/annotations/'+key.replace('/','~1')) for key in keys])
patchvm([dict(op='replace',path='/spec/runStrategy',value='Always')])
wait(lambda:get('sharedmemorychannel')['status']['phase']=='Ready')
wait(lambda:lab.ssh('kubectl get --raw=/readyz',check=False).stdout.strip()=='ok')
state=json.loads(lab.ssh('sudo cat /run/vmweave-device-plugin/status.json').stdout);assert state['ready'] and state['librarySHA256']==sha and state['generation']!=json.loads((D/'broker-before-install.json').read_text())['generation'];save('broker-after-install',state)
values=json.loads((D/'plugin-values-before.json').read_text());values['image']['repository']=refs[''].split('@')[0];values['image']['digest']=refs[''].split('@')[1];values['librarySHA256']=sha;save('plugin-values-after',values)
lab.copy(D/'plugin-values-after.json','/home/ubuntu/v0510-plugin-values.json')
r=lab.ssh('helm upgrade vmweave-device-plugin /home/ubuntu/v0510-plugin-chart.tgz -n vmweave-device-plugin -f /home/ubuntu/v0510-plugin-values.json --wait --timeout=180s && kubectl -n vmweave-device-plugin rollout status ds/vmweave-device-plugin --timeout=120s');(D/'plugin-upgrade.txt').write_text(r.stdout+r.stderr)
wait(lambda:json.loads(lab.ssh('kubectl get node dp-dev-20261105 -o json').stdout)['status']['allocatable'].get('vmweave.io/gpu')=='1')
assert json.loads(lab.ssh('helm get values vmweave-device-plugin -n vmweave-device-plugin -o json').stdout)==values
save('plugin-helm-after',json.loads(lab.ssh('helm status vmweave-device-plugin -n vmweave-device-plugin -o json').stdout));save('plugin-pods-after',json.loads(lab.ssh('kubectl -n vmweave-device-plugin get pods -o json').stdout));save('guest-node-after',json.loads(lab.ssh('kubectl get nodes -o json').stdout))
for kind in ['vm','vmi','sharedmemorychannel']:save(kind+'-after',get(kind))
worker=get('sharedmemorychannel')['status']['resourcePrefix']+'-worker';save('worker-pod-after',get('pod',worker));(D/'worker-binaries.txt').write_text(k('exec',worker,'--','sha256sum','/opt/vmweave/bin/vmweave-shm-worker','/opt/vmweave/bin/vmweave-shm-session-worker'))
save('rollout-result',dict(status='PASS',sourceRevision=source,images=images,pluginImages=identities,guestLibrarySHA256=sha,workerPod=worker));print('PAIRED PUBLIC RUNTIME READY',flush=True)
