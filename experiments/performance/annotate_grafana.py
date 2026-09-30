"""Add actual recorded experiment events to the provisioned Grafana dashboard."""
import base64,urllib.request
from common import *
m=json.loads((BASE/'monitor.json').read_text());auth=json.loads((BASE/'grafana-auth.json').read_text())
headers={'Authorization':'Basic '+base64.b64encode((auth['user']+':'+auth['password']).encode()).decode(),'Content-Type':'application/json'}
def request(path,body=None):
 r=urllib.request.Request(m['grafana']+path,headers=headers,data=json.dumps(body).encode() if body is not None else None)
 return json.load(urllib.request.urlopen(r,timeout=30))
dashboard=request('/api/dashboards/uid/vmweave-performance')['dashboard'];dashboard_id=dashboard['id']
for run in sorted((OUT/'runs').iterdir()):
 if not run.name.startswith('perf-') or not (run/'cleanup.json').exists() or (run/'grafana-annotations.json').exists():continue
 identity=json.loads((run/'identity.json').read_text());offset=identity.get('clock_offset',0);records=[]
 for line in (run/'stdout.jsonl').read_text().splitlines():
  try:r=json.loads(line)
  except ValueError:continue
  if r.get('event') not in ['MEASUREMENT_START','MEASUREMENT_END','IDLE_HOLD_START']:continue
  body={'dashboardId':dashboard_id,'time':round((r['utc']-offset)*1000),'tags':['vmweave-performance',run.name],
    'text':run.name+' '+r['event']+' '+r.get('phase','')+' (actual recorded event, guest offset corrected)'}
  records.append({'request':body,'response':request('/api/annotations',body)})
 save(run/'grafana-annotations.json',records)
print('Recorded events annotated in actual Grafana.')
