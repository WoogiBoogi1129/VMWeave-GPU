"""Export actual Prometheus ranges, dashboard JSON and original collector data."""
import argparse,base64,gzip,json,shutil,time,urllib.parse,urllib.request,csv
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('base',type=Path);p.add_argument('output',type=Path);a=p.parse_args();b=a.base;o=a.output;m=o/'monitoring';m.mkdir(exist_ok=True)
windows=list(csv.DictReader((o/'window-summary.csv').open()));start=min(float(w['start_host_utc']) for w in windows)-15;end=max(float(w['end_host_utc']) for w in windows)+15
queries={'gpu_util':'perf_gpu_util_percent','gpu_memory':'perf_gpu_memory_mib','gpu_temperature':'perf_gpu_temperature_c','gpu_sm_clock':'perf_gpu_sm_clock_mhz','gpu_mem_clock':'perf_gpu_mem_clock_mhz','gpu_power':'perf_gpu_power_w','cpu_seconds':'perf_pod_cpu_seconds_total','collector_errors':'perf_collector_errors','collector_timestamp':'perf_collector_timestamp_seconds','up':'up{job="overhead"}'}
for name,expr in queries.items():
 url='http://127.0.0.1:9098/api/v1/query_range?'+urllib.parse.urlencode({'query':expr,'start':start,'end':end,'step':'1s'})
 with urllib.request.urlopen(url,timeout=90) as r:response=json.load(r)
 assert response['status']=='success';(m/(name+'.json')).write_text(json.dumps(response,separators=(',',':'))+'\n')
for name in ['cpu.jsonl','observations.jsonl']:
 with (b/name).open('rb') as src,(m/(name+'.gz')).open('wb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as out:shutil.copyfileobj(src,out)
for name in ['prometheus.yml','dashboards/overhead.json']:
 shutil.copy2(b/'monitoring'/name,m/Path(name).name)
auth=json.loads((b/'grafana-auth.json').read_text());token=base64.b64encode((auth['user']+':'+auth['password']).encode()).decode();headers={'Authorization':'Basic '+token,'Content-Type':'application/json'}
annotations=[]
for w in windows:
 item={'dashboardUID':'overhead','time':round(float(w['start_host_utc'])*1000),'timeEnd':round(float(w['end_host_utc'])*1000),'tags':['overhead',w['session'],w['mode']],'text':w['session']+' '+w['mode']+' '+str(int(w['bytes'])//1024)+' KiB; completed='+w['completed']}
 req=urllib.request.Request('http://127.0.0.1:3301/api/annotations',data=json.dumps(item).encode(),headers=headers)
 with urllib.request.urlopen(req,timeout=10) as r:response=json.load(r)
 annotations.append({'request':item,'response':response})
(m/'annotations.json').write_text(json.dumps(annotations,indent=2)+'\n');(m/'export.json').write_text(json.dumps({'start':start,'end':end,'step_seconds':1,'queries':queries,'exported_utc':time.time()},indent=2)+'\n')
with urllib.request.urlopen('http://127.0.0.1:3301/api/dashboards/uid/overhead') as r:dashboard=json.load(r)
(m/'grafana-dashboard-api.json').write_text(json.dumps(dashboard,indent=2)+'\n')
print('Exported actual Prometheus ranges, original collectors and Grafana annotations.')
