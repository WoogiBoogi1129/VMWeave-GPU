"""After measurements, retain dashboards/data with stable Kubernetes Services."""
import os,signal,urllib.request,urllib.parse,yaml
from common import *
assert (OUT/'campaign-execution-complete.json').exists()
assert json.loads((OUT/'validation.json').read_text())['campaign_complete']
mon=json.loads((BASE/'monitor.json').read_text());ns='vmweave-performance'
assert get('namespace',ns,'default')['metadata']['uid']==json.loads((BASE/'owned-namespaces.json').read_text())[ns]['uid']
m=BASE/'monitoring';before=(m/'prometheus.yml').read_text()
(OUT/'monitoring/prometheus-during-experiments.yml').write_text(before)
# Local TSDB snapshot retains observations beyond the live retention window.
response=json.load(urllib.request.urlopen(urllib.request.Request(mon['prometheus']+'/api/v1/admin/tsdb/snapshot',data=b'',method='POST'),timeout=60))
assert response['status']=='success';save(OUT/'monitoring/tsdb-snapshot.json',response)
services={}
for name,ports in [('perf-monitor',[(3000,'grafana'),(9090,'prometheus')]),('perf-dcgm',[(9400,'metrics')]),('perf-node-exporter',[(9100,'metrics')])]:
 pod=get('pod',name,ns);assert pod
 k('label','pod',name,'-n',ns,'vmweave.io/monitor='+name,'--overwrite')
 existing=get('service',name,ns)
 if not existing:existing=create({'apiVersion':'v1','kind':'Service','metadata':{'name':name,'namespace':ns},'spec':{'selector':{'vmweave.io/monitor':name},'ports':[{'name':label,'port':port,'targetPort':port} for port,label in ports]}})
 assert existing['spec']['selector']=={'vmweave.io/monitor':name}
 services[name]=existing['spec']['clusterIP']
config=yaml.safe_load(before)
config['scrape_configs']=[job for job in config['scrape_configs'] if job['job_name']!='experiment']
for job in config['scrape_configs']:
 if job['job_name'] in ['dcgm','node']:
  service,port=('perf-dcgm',9400) if job['job_name']=='dcgm' else ('perf-node-exporter',9100)
  job['static_configs']=[{'targets':[services[service]+':'+str(port)]}]
(m/'prometheus.yml').write_text(yaml.safe_dump(config,sort_keys=False))
auth=json.loads((BASE/'grafana-auth.json').read_text())
if not get('secret','perf-grafana-auth',ns):create({'apiVersion':'v1','kind':'Secret','metadata':{'name':'perf-grafana-auth','namespace':ns},'stringData':{'password':auth['password']}},private=True)
old=get('pod','perf-monitor',ns);assert any(v.get('hostPath',{}).get('path')==str(m) for v in old['spec']['volumes'])
new={'apiVersion':'v1','kind':'Pod','metadata':{'name':'perf-monitor','namespace':ns,'labels':{'vmweave.io/monitor':'perf-monitor'}},'spec':old['spec']}
for c in new['spec']['containers']:
 if c['name']=='grafana':c['env']=[{'name':'GF_SECURITY_ADMIN_PASSWORD','valueFrom':{'secretKeyRef':{'name':'perf-grafana-auth','key':'password'}}}]
k('delete','--raw','/api/v1/namespaces/'+ns+'/pods/perf-monitor','-f','-',input=json.dumps({'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':old['metadata']['uid']}}))
wait(lambda:not get('pod','perf-monitor',ns),120);created=create(new)
wait(lambda:len((p:=get('pod','perf-monitor',ns)).get('status',{}).get('containerStatuses',[]))==2 and all(s.get('ready') for s in p['status']['containerStatuses']),180)
mon.update({'prometheus':'http://'+services['perf-monitor']+':9090','grafana':'http://'+services['perf-monitor']+':3000','dcgm':'http://'+services['perf-dcgm']+':9400','namespace':ns,'monitor_pod_uid':created['metadata']['uid']})
save(BASE/'monitor.json',mon)
def healthy():
 try:
  targets=json.load(urllib.request.urlopen(mon['prometheus']+'/api/v1/targets',timeout=5))['data']['activeTargets']
  return targets if len(targets)==3 and all(t['health']=='up' for t in targets) else None
 except Exception:return None
targets=wait(healthy,120)
save(OUT/'monitoring/kubernetes-resources.json',{'pods':[get('pod',name,ns) for name in services],'services':[get('service',name,ns) for name in services]})
save(OUT/'monitoring/prometheus-build.json',json.load(urllib.request.urlopen(mon['prometheus']+'/api/v1/status/buildinfo')))
stopped=[]
for process in json.loads((BASE/'processes.json').read_text()):
 proc=Path('/proc')/str(process['pid'])/'cmdline'
 if not proc.exists():continue
 args=proc.read_bytes().replace(b'\0',b' ').decode()
 expected='experiments/performance/exporter.py' if process['name']=='app-exporter' else 'nvidia-smi pmon -i 1'
 assert expected in args,('PID has different owner',process['name'],process['pid'])
 os.kill(process['pid'],signal.SIGTERM);stopped.append({'name':process['name'],'pid':process['pid'],'utc':time.time()})
save(OUT/'monitoring/retained.json',{'utc':time.time(),'services':services,'targets':[{k:t[k] for k in ['labels','health','scrapeUrl','lastError']} for t in targets],'stopped_measurement_collectors':stopped,'grafana_health':json.load(urllib.request.urlopen(mon['grafana']+'/api/health')),'history':'Full measurement query responses are in runs/*/telemetry.json; live TSDB retained 30 days, local snapshot retained under monitoring/prom-data/snapshots.','credentials':'Grafana now uses a Kubernetes Secret reference; anonymous Viewer remains enabled.','port_forward':'kubectl -n vmweave-performance port-forward svc/perf-monitor 3000:3000 9090:9090'})
print('Monitoring retained with healthy stable Services; measurement-only collectors stopped.')
