"""Audit campaign cleanup and stop only this campaign's local exporter."""
from common import *
import signal, urllib.request, urllib.parse

assert json.loads((OUT/'cleanup-complete.json').read_text())['monitoring_retained']
remaining=[];preserved=[]
for ns in [NS,'vmweave-performance-tcp']:
 objects=json.loads(k('get','pods,vm,vmi,pvc,gpuprofiles,gpurequests,sharedmemorychannels','-n',ns,'-o','json'))['items']
 for obj in objects:
  item={'namespace':ns,'kind':obj['kind'],'name':obj['metadata']['name'],'uid':obj['metadata']['uid']}
  (remaining if item['name'].startswith(('sc-','scprofile-','virt-launcher-sc-')) else preserved).append(item)
for obj in json.loads(k('get','pv','-o','json'))['items']:
 if obj['metadata']['name'].startswith('sc-'):remaining.append({'kind':'PersistentVolume','name':obj['metadata']['name']})
assert not remaining,remaining
inventory=call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
target='\n'.join(line for line in inventory.splitlines() if GPU in line)
assert not target,target
stopped=[]
for entry in Path('/proc').iterdir():
 if not entry.name.isdigit():continue
 try:args=(entry/'cmdline').read_bytes().split(b'\0')
 except (PermissionError,FileNotFoundError,ProcessLookupError):continue
 if b'experiments/system-comparison/exporter.py' not in args:continue
 pid=int(entry.name);os.kill(pid,signal.SIGTERM);stopped.append(pid)
assert len(stopped)==1,stopped
monitor=json.loads((BASE/'monitor.json').read_text())
health=json.load(urllib.request.urlopen(monitor['prometheus']+'/api/v1/query?'+urllib.parse.urlencode({'query':'up'}),timeout=20))
assert health['status']=='success'
for job in ['dcgm','hami','node']:
 values=[x for x in health['data']['result'] if x['metric']['job']==job]
 assert values and all(x['value'][1]=='1' for x in values),(job,values)
save(OUT/'final-audit.json',{'utc':time.time(),'remaining_campaign_resources':remaining,'target_gpu_compute_processes':target,'monitoring_health':health,'exporter_stop_pid':stopped[0],'preserved_namespace_resources':preserved})
print('PASS: own resources removed, target GPU idle, common monitoring healthy, exporter stopped')
