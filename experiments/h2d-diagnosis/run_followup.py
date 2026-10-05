"""Fresh five-repeat causal controls and uninstrumented confirmation."""
from run_diagnostic import *
ensure_admin()
protocol=json.loads((OUT/'protocol-followup.json').read_text())
for item in protocol['sessions']:
 name=item['name']
 if (OUT/'runs'/name/'cleanup.json').exists():
  assert not (OUT/'runs'/name/'failure.json').exists();continue
 one(name,item['variant'],metrics=item['metrics'],mode=item['mode'],seconds=item['seconds'],warmup=item['warmup'],pattern_order=item.get('pattern_order',0),worker_cpus=item.get('worker_cpus'),map_probe=item.get('map_probe',False))
save(OUT/'followup-complete.json',{'sessions':len(protocol['sessions']),'utc':time.time()})
