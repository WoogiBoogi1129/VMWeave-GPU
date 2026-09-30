#!/usr/bin/env python3
"""Checkpointed, stopped-allocation migration. Default is a read-only plan.

Never copies status/finalizers/Attachments. Old APIs remain installed for history.
Requires old controllers stopped, old channels Released, and referenced VMs Halted.
"""
import argparse,json,pathlib,subprocess,re
p=argparse.ArgumentParser();p.add_argument('--namespace',required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--apply',action='store_true');p.add_argument('--channel',action='append',default=[],help='Only selected channels are recreated; completed history is not restarted');p.add_argument('--worker-image');p.add_argument('--helper-image');p.add_argument('--hook-image');a=p.parse_args()
def k(*xs,input=None):return subprocess.check_output(['kubectl',*xs],input=json.dumps(input) if input is not None else None,text=True)
def get(kind,name=None):
 raw=k('get',kind,*([name] if name else []),'-n',a.namespace,'--ignore-not-found','-o','json');return json.loads(raw) if raw.strip() else None
def items(kind):return (get(kind) or {}).get('items',[])
a.output.mkdir(parents=True,exist_ok=True);a.output.chmod(0o700)
old={n:items('flyt'+n+'.flyt.dev') for n in ['gpuprofiles','gpurequests','sharedmemorychannels','channelattachments']}
for n,values in old.items():
 f=a.output/('before-'+n+'.json')
 if not f.exists():f.write_text(json.dumps(values,indent=2)+'\n');f.chmod(0o600)
blocked=[{'name':c['metadata']['name'],'phase':c.get('status',{}).get('phase')} for c in old['sharedmemorychannels'] if c.get('status',{}).get('phase')!='Released']
report={'namespace':a.namespace,'apply':a.apply,'blockedChannels':blocked,'counts':{n:len(v) for n,v in old.items()},'selectedChannels':a.channel,'mapping':[]}
(a.output/'plan.json').write_text(json.dumps(report,indent=2)+'\n')
if not a.apply:print(json.dumps(report,indent=2));raise SystemExit(0)
if a.channel and not all([a.worker_image,a.helper_image,a.hook_image]):raise SystemExit('channel migration requires new helper, worker and hook image digests')
if set(a.channel)-{c['metadata']['name'] for c in old['sharedmemorychannels']}:raise SystemExit('unknown selected channel')
for image in [a.worker_image,a.helper_image,a.hook_image]:
 if image and not re.fullmatch(r'[^\s]+@sha256:[0-9a-f]{64}',image):raise SystemExit('digest-pinned images required')
if blocked:raise SystemExit('unreleased legacy allocations block migration; see plan.json')
for d in items('deployments'):
 for c in d['spec']['template']['spec']['containers']:
  env={x['name']:x.get('value') for x in c.get('env',[])}
  if env.get('FLYT_MODE')=='active' and d['spec'].get('replicas',1)>0:raise SystemExit('stop legacy deployment first: '+d['metadata']['name'])
if items('virtualmachineinstances.kubevirt.io'):raise SystemExit('VMI still running; stop before migration')
# Validate every dependency before creating any new object.
profile_uids={x['metadata']['uid'] for x in old['gpuprofiles']}
request_uids={x['metadata']['uid'] for x in old['gpurequests']}
for o in old['gpurequests']:
 s=o['spec'];vm=get('virtualmachines.kubevirt.io',s['vmRef']['name'])
 if not vm or vm['metadata']['uid']!=s['vmRef']['uid'] or vm['spec'].get('runStrategy')!='Halted':raise SystemExit('VM not halted or UID mismatch: '+s['vmRef']['name'])
 if s['profileRef']['uid'] not in profile_uids:raise SystemExit('missing old profile UID')
for o in old['sharedmemorychannels']:
 if o['metadata']['name'] not in a.channel:continue
 s=o['spec'];pvc=get('pvc',s['pvcRef']['name'])
 if not pvc or pvc['metadata']['uid']!=s['pvcRef']['uid']:raise SystemExit('PVC UID mismatch')
 if s['requestRef']['uid'] not in request_uids:raise SystemExit('missing old request UID')
lookup={}
def defaults(plural,spec):
 schema=json.loads((pathlib.Path(__file__).resolve().parents[2]/'operator/config/crd/bases'/(plural+'.vmweave.io.json')).read_text())['spec']['versions'][0]['schema']['openAPIV3Schema']['properties']['spec']
 spec=dict(spec)
 for name,field in schema['properties'].items():
  if name not in spec and 'default' in field:spec[name]=field['default']
 return spec
def create(kind,plural,oldobj,spec):
 spec=defaults(plural,spec)
 m=oldobj['metadata'];name=m['name'];target={'apiVersion':'vmweave.io/v1alpha1','kind':kind,'metadata':{'name':name,'namespace':a.namespace,'annotations':{'vmweave.io/migrated-from-uid':m['uid']}},'spec':spec}
 existing=get(plural+'.vmweave.io',name)
 if existing:
  comparison=dict(existing['spec'])
  # A rerun must preserve a later drain request, never reactivate completed work.
  if kind=='SharedMemoryChannel':comparison['drain']=spec.get('drain',False)
  if existing['metadata'].get('annotations',{}).get('vmweave.io/migrated-from-uid')!=m['uid'] or comparison!=spec:raise SystemExit('target collision/spec mismatch: '+kind+'/'+name)
 else:existing=json.loads(k('create','-f','-','-o','json',input=target))
 new={'name':name,'uid':existing['metadata']['uid']};lookup[m['uid']]=new
 report['mapping'].append({'kind':kind,'name':name,'oldUID':m['uid'],'newUID':new['uid']});(a.output/'checkpoint.json').write_text(json.dumps(report,indent=2)+'\n');return existing
for o in old['gpuprofiles']:
 spec=dict(o['spec'])
 if a.worker_image:spec['workerImage']=a.worker_image
 create('GPUProfile','gpuprofiles',o,spec)
for o in old['gpurequests']:
 s=dict(o['spec']);vm=get('virtualmachines.kubevirt.io',s['vmRef']['name'])
 if not vm or vm['metadata']['uid']!=s['vmRef']['uid'] or vm['spec'].get('runStrategy')!='Halted':raise SystemExit('VM not halted or UID mismatch: '+s['vmRef']['name'])
 s['profileRef']=lookup[s['profileRef']['uid']];create('GPURequest','gpurequests',o,s)
for o in old['sharedmemorychannels']:
 if o['metadata']['name'] not in a.channel:continue
 s=dict(o['spec']);s['requestRef']=lookup[s['requestRef']['uid']];s['drain']=False
 s.update(image=a.helper_image,workerImage=a.worker_image,hookImage=a.hook_image)
 vm=get('virtualmachines.kubevirt.io',s['vmRef']['name']);pvc=get('pvc',s['pvcRef']['name'])
 if not vm or vm['metadata']['uid']!=s['vmRef']['uid'] or vm['spec'].get('runStrategy')!='Halted':raise SystemExit('VM changed during migration')
 if not pvc or pvc['metadata']['uid']!=s['pvcRef']['uid']:raise SystemExit('PVC UID mismatch')
 annotations=vm['spec']['template'].get('metadata',{}).get('annotations',{})
 if annotations.get('flyt.dev/shm-channel-uid') not in (None,o['metadata']['uid']):raise SystemExit('foreign legacy binding')
 existing=get('sharedmemorychannels.vmweave.io',o['metadata']['name'])
 if existing:
  create('SharedMemoryChannel','sharedmemorychannels',o,s)
  continue
 if annotations.get('vmweave.io/shm-channel'):raise SystemExit('VM already has a different new binding')
 before=a.output/('vm-before-'+vm['metadata']['name']+'.json')
 if not before.exists():before.write_text(json.dumps(vm,indent=2));before.chmod(0o600)
 for key in list(annotations):
  if key.startswith('flyt.dev/shm-') or key=='hooks.kubevirt.io/hookSidecars':del annotations[key]
 k('replace','-f','-',input=vm)
 create('SharedMemoryChannel','sharedmemorychannels',o,s)
report['status']='selected resources migrated; unselected historical channels retained'
(a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
