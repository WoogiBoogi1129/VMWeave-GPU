#!/usr/bin/env python3
"""Create a Request and Channel with fetched same-namespace UID references."""
import argparse,json,re,subprocess
p=argparse.ArgumentParser()
for n in ['namespace','vm','profile','pvc','name','helper-image','hook-image']:p.add_argument('--'+n,required=True)
p.add_argument('--compute',type=int,required=True);p.add_argument('--memory',required=True);p.add_argument('--sessions',type=int,default=1);p.add_argument('--uid',type=int,default=107);p.add_argument('--gid',type=int,default=107);a=p.parse_args()
def k(*xs,input=None):return json.loads(subprocess.check_output(['kubectl',*xs,'-o','json'],input=json.dumps(input) if input else None,text=True))
def get(kind,name):return k('get',kind,name,'-n',a.namespace)
def ref(o):return {x:o['metadata'][x] for x in ['name','uid']}
vm=get('virtualmachines.kubevirt.io',a.vm);profile=get('gpuprofiles.vmweave.io',a.profile);pvc=get('pvc',a.pvc)
if vm['spec'].get('runStrategy')!='Halted':raise SystemExit('VM must be Halted')
if not profile['spec'].get('approved'):raise SystemExit('Profile must be approved')
for image in [a.helper_image,a.hook_image,profile['spec']['workerImage']]:
 if not re.fullmatch(r'.+@sha256:[0-9a-f]{64}',image):raise SystemExit('digest-pinned images required')
meta={'name':a.name,'namespace':a.namespace}
q=k('create','-f','-',input={'apiVersion':'vmweave.io/v1alpha1','kind':'GPURequest','metadata':meta,'spec':{'vmRef':ref(vm),'profileRef':ref(profile),'count':1,'compute':a.compute,'memory':a.memory}})
c=k('create','-f','-',input={'apiVersion':'vmweave.io/v1alpha1','kind':'SharedMemoryChannel','metadata':meta,'spec':{'vmRef':ref(vm),'requestRef':ref(q),'pvcRef':ref(pvc),'sessions':a.sessions,'uid':a.uid,'gid':a.gid,'image':a.helper_image,'workerImage':profile['spec']['workerImage'],'hookImage':a.hook_image}})
print(json.dumps({'request':ref(q),'channel':ref(c)},indent=2))
