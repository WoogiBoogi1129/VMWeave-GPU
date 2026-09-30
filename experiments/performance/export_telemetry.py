"""Export retained Prometheus observations with raw query and absolute window."""
import urllib.request,urllib.parse
from common import *
monitor=json.loads((BASE/'monitor.json').read_text())
queries={'gpu_util':'DCGM_FI_DEV_GPU_UTIL and on(instance) (up{job="dcgm"} == 1)',
 'gpu_memory':'DCGM_FI_DEV_FB_USED','gpu_power':'DCGM_FI_DEV_POWER_USAGE','gpu_clock':'DCGM_FI_DEV_SM_CLOCK','gpu_temperature':'DCGM_FI_DEV_GPU_TEMP',
 'hami_util':'hami_container_device_utilization_ratio{namespace="vmweave-test-a"} and on(instance) (up{job="hami"} == 1)','collector_health':'up','application_completed':'vmweave_completed_total',
 'application_latency':'vmweave_last_operation_latency_seconds','pod_cpu':'vmweave_pod_cpu_seconds_total','host_cpu':'node_cpu_seconds_total{mode="idle"}'}
for run in sorted((OUT/'runs').iterdir()):
 if not (run/'execution.json').exists() or (run/'telemetry.json').exists():continue
 events=[json.loads(l) for l in (run/'stdout.jsonl').read_text().splitlines() if l.startswith('{')]
 events=[x for x in events if 'utc' in x]
 if not events:continue
 identity=json.loads((run/'identity.json').read_text());offset=identity.get('clock_offset',0)
 start=min(x['utc'] for x in events)-offset-5;end=max(x['utc'] for x in events)-offset+5
 responses={}
 for name,query in queries.items():
  params={'query':query,'start':start,'end':end,'step':1}
  data=json.load(urllib.request.urlopen(monitor['prometheus']+'/api/v1/query_range?'+urllib.parse.urlencode(params),timeout=60))
  if data.get('status')!='success':raise RuntimeError(data)
  responses[name]={'query':params,**data}
 save(run/'telemetry.json',responses);print('EXPORTED',run.name,flush=True)
