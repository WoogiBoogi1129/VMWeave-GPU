"""Record external Pod identity/readiness changes without touching workloads."""
from lab import *
stop=B/'observer.stop'
assert not stop.exists()
last=None
with (O/'external-pods.jsonl').open('x') as f:
 while not stop.exists():
  try:
   rows=[]
   for p in json.loads(k('get','pods','-A','-o','json',timeout=20))['items']:
    if p['metadata']['namespace']==NS or p['metadata']['name'].startswith(('tt-','virt-launcher-tt-')):continue
    rows.append({'namespace':p['metadata']['namespace'],'name':p['metadata']['name'],'uid':p['metadata']['uid'],'phase':p['status'].get('phase'),'containers':[{z:c.get(z) for z in ['name','imageID','ready','restartCount']} for c in p['status'].get('containerStatuses',[])]})
   digest=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
   f.write(json.dumps({'utc':time.time(),'digest':digest,'pods':rows if digest!=last else None})+'\n');f.flush();last=digest
  except Exception as e:f.write(json.dumps({'utc':time.time(),'error':type(e).__name__})+'\n');f.flush()
  for _ in range(15):
   if stop.exists():break
   time.sleep(1)
