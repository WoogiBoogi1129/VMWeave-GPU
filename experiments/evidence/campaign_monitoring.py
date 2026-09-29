"""Write localhost Prometheus/Grafana configuration, pinned runtime supplied separately."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);a=p.parse_args();b=a.base.resolve()
m=b/'monitoring';m.mkdir(exist_ok=True)
(m/'prometheus.yml').write_text('global:\n  scrape_interval: 1s\n  scrape_timeout: 900ms\nscrape_configs:\n  - job_name: flyt-campaign\n    static_configs:\n      - targets: ["127.0.0.1:9899"]\n')
for sub in ['provisioning/datasources','provisioning/dashboards','dashboards','grafana-data','grafana-logs']:(m/sub).mkdir(parents=True,exist_ok=True)
(m/'provisioning/datasources/prometheus.yaml').write_text('apiVersion: 1\ndatasources:\n  - name: Campaign Prometheus\n    uid: campaign-prom\n    type: prometheus\n    access: proxy\n    url: http://127.0.0.1:9099\n    isDefault: true\n    jsonData:\n      timeInterval: 1s\n')
(m/'provisioning/dashboards/campaign.yaml').write_text('apiVersion: 1\nproviders:\n  - name: Campaign\n    type: file\n    options:\n      path: '+str(m/'dashboards')+'\n')
(m/'grafana.ini').write_text(f'''[server]
http_addr = 127.0.0.1
http_port = 3300
[paths]
data = {m/'grafana-data'}
logs = {m/'grafana-logs'}
provisioning = {m/'provisioning'}
[auth.anonymous]
enabled = true
org_role = Viewer
[security]
allow_embedding = true
[analytics]
reporting_enabled = false
check_for_updates = false
''')
ds={'type':'prometheus','uid':'campaign-prom'}
panels=[]
specs=[('Physical GPU utilization — entire device','flyt_gpu_utilization_percent','percent'),
('GPU physical memory','flyt_gpu_memory_mib','mebibytes'),
('Run active — warmup + measurement','flyt_run_active{run_id=~"$run"}','short'),
('HAMi container memory','hami_container_device_memory_bytes{pod=~"evidence-c28-.*"}','bytes'),
('Completed synchronized kernels / second (live estimate)','rate(flyt_completed_work_total{run_id=~"$run"}[5s])','ops'),
('Final elapsed seconds (completed runs)','flyt_run_elapsed_seconds{run_id=~"$run"}','s'),
('Final output mismatches (check count below)','flyt_run_mismatches{run_id=~"$run"}','short'),
('Final throughput (completed work / actual elapsed)','flyt_run_throughput{run_id=~"$run"}','ops'),
('Final checked elements (0 = reference generation)','flyt_run_checked_elements{run_id=~"$run"}','short'),
('Scrape health (1 = reachable)','up{job="flyt-campaign"}','short')]
for i,(title,expr,unit) in enumerate(specs):
 panels.append({'id':i+1,'type':'timeseries','title':title,'datasource':ds,'gridPos':{'x':(i%2)*12,'y':(i//2)*8,'w':12,'h':8},'targets':[{'expr':expr,'refId':'A','legendFormat':'{{run_id}}{{pod}}'}],'fieldConfig':{'defaults':{'unit':unit,'custom':{'drawStyle':'line','lineWidth':2,'spanNulls':False}},'overrides':[]},'options':{'legend':{'displayMode':'list','placement':'bottom'}}})
d={'uid':'flyt-campaign','title':'FLYT campaign — actual SHM / HAMi experiments','schemaVersion':40,'version':1,'timezone':'utc','refresh':'5s','time':{'from':'now-15m','to':'now'},'tags':['actual-measurements','2026-09-28'],'templating':{'list':[{'name':'run','label':'Run ID','type':'query','datasource':ds,'query':'label_values(flyt_run_active, run_id)','refresh':1,'multi':True,'includeAll':True,'allValue':'.*','current':{'text':'All','value':'$__all'}}]},'panels':panels,'annotations':{'list':[{'name':'Run state','datasource':ds,'enable':True,'expr':'changes(flyt_run_active{run_id=~"$run"}[5s]) > 0','titleFormat':'Observed state change','textFormat':'{{run_id}}'}]}}
(m/'dashboards/campaign.json').write_text(json.dumps(d,indent=2))
# Detailed annotations come from actual event timestamps, independently of the
# collector's sampled active gauge. Keep the sampled overlay disabled by default.
d['annotations']['list'][0]['enable']=False
d['annotations']['list'].append({'name':'Recorded experiment events','type':'dashboard',
 'datasource':{'type':'grafana','uid':'-- Grafana --'},'enable':True,'hide':False,
 'iconColor':'rgba(255, 180, 60, 1)','target':{'type':'tags','tags':['flyt-campaign'],'matchAny':False,'limit':1000}})
(m/'dashboards/campaign.json').write_text(json.dumps(d,indent=2))
print(m)
