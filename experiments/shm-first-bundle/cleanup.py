"""Remove only this campaign's UID-matched, Released resources and image refs."""
from common import *
import yaml

assert json.loads((OUT/'validation.json').read_text())['complete']
records={}
def remember(x):
 m=x['metadata'];name=m['name'];ns=m.get('namespace','')
 if not name.startswith(('sf-','shmfirst-','shm-first-')):raise ValueError(name)
 records[(x['kind'],ns,name)]=x
for line in (OUT/'commands.jsonl').read_text().splitlines():
 e=json.loads(line);cmd=e['command']
 if len(cmd)>1 and cmd[:2]==['kubectl','create'] and not e['exit_code']:
  try:remember(json.loads(e['stdout']))
  except (ValueError,KeyError):pass
for p in (OUT/'runs').glob('sf-*/channel-released.json'):
 x=json.loads(p.read_text());assert x['status']['phase']=='Released';remember(x)
 for kind,key in [('gpurequests.vmweave.io','requestRef'),('vm','vmRef'),('pvc','pvcRef')]:
  ref=x['spec'][key];r=get(kind,ref['name'])
  if r:assert r['metadata']['uid']==ref['uid'];remember(r)
plural={'SharedMemoryChannel':'sharedmemorychannels','GPURequest':'gpurequests','VirtualMachine':'virtualmachines','PersistentVolumeClaim':'persistentvolumeclaims','PersistentVolume':'persistentvolumes','GPUProfile':'gpuprofiles','Pod':'pods'}
order={k:i for i,k in enumerate(plural)};removed=[]
for (kind,ns,name),saved in sorted(records.items(),key=lambda x:(x[0][2]==HELPER,order[x[0][0]],x[0][2])):
 if name==HELPER:continue
 api=saved['apiVersion'];resource=plural[kind]+('.'+api.split('/')[0] if '/' in api else '')
 current=get(resource,name,ns)
 if not current:continue
 assert current['metadata']['uid']==saved['metadata']['uid']
 if kind=='SharedMemoryChannel':assert current['status']['phase']=='Released'
 if kind=='VirtualMachine':assert current['spec']['runStrategy']=='Halted'
 if kind=='PersistentVolume':
  assert current['spec']['local']['path']=='/var/lib/vmweave/shm-first-20261001/'+name
  admin(['rmdir','/host'+current['spec']['local']['path']])
 path=('/api/'+api if '/' not in api else '/apis/'+api)+('/namespaces/'+ns if ns else '')+'/'+plural[kind]+'/'+name
 body={'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':current['metadata']['uid']},'propagationPolicy':'Background' if kind=='SharedMemoryChannel' else 'Foreground'}
 k('delete','--raw',path,'-f','-',input=json.dumps(body));wait(lambda:not get(resource,name,ns),180)
 removed.append({'kind':kind,'name':name,'uid':current['metadata']['uid']});save(OUT/'cleanup-resources.json',removed)
for item in json.loads((BASE/'retained-images.json').read_text()):
 current=json.loads(admin(['chroot','/host','podman','container','inspect',item['container_id']]))[0]
 assert current['Id']==item['container_id'] and not current['State']['Running']
 assert current['Config']['Labels']['vmweave.campaign']=='shm-first-20261001'
 admin(['chroot','/host','podman','rm',item['container_id']])
p=ROOT/'.local/performance-20260930/monitoring/prometheus.yml';config=yaml.safe_load(p.read_text())
config['scrape_configs']=[x for x in config['scrape_configs'] if x['job_name']!='shm-first'];p.write_text(yaml.safe_dump(config,sort_keys=False))
k('exec','-n','vmweave-performance','perf-monitor','-c','prometheus','--','sh','-c','kill -HUP 1')
saved=records[('Pod',NS,HELPER)];current=get('pod',HELPER);assert current['metadata']['uid']==saved['metadata']['uid']
k('delete','--raw','/api/v1/namespaces/'+NS+'/pods/'+HELPER,'-f','-',input=json.dumps({'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':current['metadata']['uid']}}))
wait(lambda:not get('pod',HELPER),90)
save(OUT/'cleanup-complete.json',{'utc':time.time(),'resources':len(removed),'image_references_removed':True,'monitoring_retained':True})
