"""Delete only campaign-owned resources, with API UID preconditions, after verification."""
from common import *
import urllib.parse
assert json.loads((OUT/'validation.json').read_text())['campaign_complete']
assert (OUT/'campaign-execution-complete.json').exists()
records={}
def remember(x):
 m=x['metadata'];ns=m.get('namespace','');name=m['name']
 if ns not in [NS,'vmweave-performance-tcp',''] or not name.startswith(('perf-','pilot-')):return
 records[(x['kind'],ns,name)]=x
for line in (OUT/'commands.jsonl').read_text().splitlines():
 try:
  entry=json.loads(line);cmd=entry['command']
  if len(cmd)>1 and cmd[0]=='kubectl' and cmd[1]=='create' and entry['exit_code']==0:remember(json.loads(entry['stdout']))
 except (ValueError,KeyError,TypeError):continue
for run in (OUT/'runs').iterdir():
 released=run/'channel-released.json'
 if released.exists():
  x=json.loads(released.read_text());assert x['status']['phase']=='Released';remember(x)
  for kind,key in [('gpurequests.vmweave.io','requestRef'),('vm','vmRef'),('pvc','pvcRef')]:
   ref=x['spec'][key];resource=get(kind,ref['name'])
   if resource:
    assert resource['metadata']['uid']==ref['uid'];remember(resource)
for item in json.loads((BASE/'owned-infrastructure.json').read_text()):
 x=get(item['kind'],item['name'],item['namespace'])
 if x:
  assert x['metadata']['uid']==item['uid'];remember(x)
# The isolated manager is recreated per T session; its current UID is authoritative.
legacy=json.loads((BASE/'legacy.json').read_text());manager=get('pod','perf-tcp-manager')
if manager:assert manager['metadata']['uid']==legacy['manager_uid'];remember(manager)
priority={'SharedMemoryChannel':0,'GPURequest':1,'VirtualMachine':2,'PersistentVolumeClaim':3,'PersistentVolume':4,'GPUProfile':5,'Pod':6}
plural={'SharedMemoryChannel':'sharedmemorychannels','GPURequest':'gpurequests','VirtualMachine':'virtualmachines','PersistentVolumeClaim':'persistentvolumeclaims','PersistentVolume':'persistentvolumes','GPUProfile':'gpuprofiles','Pod':'pods'}
removed=[];already_absent=[]
for (kind,ns,name),saved in sorted(records.items(),key=lambda x:(x[0][2]==HELPER,priority.get(x[0][0],99),x[0][2])):
 if kind not in plural:raise RuntimeError('Review unhandled owned kind '+kind)
 api=saved['apiVersion'];resource=plural[kind]+('.'+api.split('/')[0] if '/' in api else '')
 current=get(resource,name,ns)
 if not current:already_absent.append({'kind':kind,'name':name,'uid':saved['metadata']['uid']});continue
 assert current['metadata']['uid']==saved['metadata']['uid'],('UID changed',kind,name)
 if kind=='SharedMemoryChannel':assert current['status']['phase']=='Released'
 if kind=='VirtualMachine':assert current['spec']['runStrategy']=='Halted'
 if kind=='PersistentVolume':
  assert current['spec']['local']['path']=='/var/lib/vmweave/performance-20260930/'+name
  # Empty backing only: do not erase unexpected files.
  admin(['rmdir','/host'+current['spec']['local']['path']])
 path=('/api/'+api if '/' not in api else '/apis/'+api)+('/namespaces/'+ns if ns else '')+'/'+plural[kind]+'/'+name
 body={'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':current['metadata']['uid']},'propagationPolicy':'Foreground'}
 response=k('delete','--raw',path,'-f','-',input=json.dumps(body))
 wait(lambda:not get(resource,name,ns),180)
 removed.append({'kind':kind,'namespace':ns,'name':name,'uid':current['metadata']['uid'],'utc':time.time()})
 print('REMOVED',kind,ns,name,flush=True)
save(OUT/'cleanup-resources.json',{'removed':removed,'already_absent':already_absent,'utc':time.time(),'scope':'UID-matched campaign resources only; monitoring namespace retained'})
