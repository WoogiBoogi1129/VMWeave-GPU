"""Expose actual application progress; stale runs disappear rather than hold zero."""
import http.server,json,time,os
from pathlib import Path
from common import BASE,OUT
os.sched_setaffinity(0,{48,49,50,51})
class Handler(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  try:states=json.loads((BASE/'live-state.json').read_text())
  except (FileNotFoundError,ValueError):states={}
  lines=['# TYPE vmweave_completed_total counter','# TYPE vmweave_compute_cap_percent gauge','# TYPE vmweave_phase gauge']
  for name,r in states.items():
   if time.time()-r['updated']>5:continue
   labels='run_id='+json.dumps(name)+',vm='+json.dumps(r['path'])+',phase='+json.dumps(r.get('phase','workload'))
   lines += ['vmweave_completed_total{'+labels+'} '+str(r.get('completed',0)),
      'vmweave_compute_cap_percent{'+labels+'} '+str(r['cap']),
      'vmweave_phase{'+labels+'} '+str({'WARMUP_START':0,'WAIT_START':1,'MEASUREMENT_START':2,'TICK':2,'MEASUREMENT_END':3,'RESULT':3}.get(r.get('event'),0))]
   if 'last_latency_s' in r:lines.append('vmweave_last_operation_latency_seconds{'+labels+'} '+str(r['last_latency_s']))
   try:
    identity=json.loads((OUT/'runs'/name/'identity.json').read_text())
    uids={role:identity[key] for role,key in [('native','pod_uid'),('worker','worker_uid'),('cell','cell_uid'),('launcher','launcher_uid')] if key in identity}
    observations=[]
    for cg in Path('/sys/fs/cgroup/kubepods.slice').glob('*/*pod*.slice'):
     for role,uid in uids.items():
      if uid not in cg.name and uid.replace('-','_') not in cg.name:continue
      vals={k:int(v) for k,v in (line.split() for line in (cg/'cpu.stat').read_text().splitlines())}
      memory=int((cg/'memory.current').read_text());cl='{run_id='+json.dumps(name)+',role='+json.dumps(role)+'}'
      lines.extend(['vmweave_pod_cpu_seconds_total'+cl+' '+str(vals['usage_usec']/1e6),'vmweave_pod_memory_bytes'+cl+' '+str(memory)])
      observations.append({'role':role,'uid':uid,'cpu':vals,'memory_bytes':memory})
    with (OUT/'monitoring/cpu.jsonl').open('a') as f:f.write(json.dumps({'utc':time.time(),'run_id':name,'pods':observations})+'\n')
   except (FileNotFoundError,ValueError):pass
  data=('\n'.join(lines)+'\n').encode();self.send_response(200);self.send_header('Content-Type','text/plain; version=0.0.4');self.end_headers();self.wfile.write(data)
 def log_message(self,*a):pass
http.server.ThreadingHTTPServer(('0.0.0.0',9899),Handler).serve_forever()

