from pathlib import Path
import json,os,secrets,subprocess,time,urllib.request
base=Path('.local/stage3-20260929').resolve();m=base/'monitoring';m.mkdir()
for sub in ['provisioning/datasources','provisioning/dashboards','dashboards','grafana-data','grafana-logs']:(m/sub).mkdir(parents=True,exist_ok=True)
(m/'prometheus.yml').write_text('global:\n  scrape_interval: 1s\n  scrape_timeout: 900ms\nscrape_configs:\n  - job_name: stage3\n    static_configs:\n      - targets: ["127.0.0.1:9898"]\n')
(m/'provisioning/datasources/prometheus.yaml').write_text('apiVersion: 1\ndatasources:\n  - name: Stage3 Prometheus\n    uid: stage3-prom\n    type: prometheus\n    access: proxy\n    url: http://127.0.0.1:9098\n    isDefault: true\n    jsonData:\n      timeInterval: 1s\n')
(m/'provisioning/dashboards/stage3.yaml').write_text('apiVersion: 1\nproviders:\n  - name: Stage3\n    type: file\n    options:\n      path: '+str(m/'dashboards')+'\n')
(m/'grafana.ini').write_text(f'[server]\nhttp_addr = 127.0.0.1\nhttp_port = 3301\n[paths]\ndata = {m}/grafana-data\nlogs = {m}/grafana-logs\nprovisioning = {m}/provisioning\n[auth.anonymous]\nenabled = true\norg_role = Viewer\n[analytics]\nreporting_enabled = false\ncheck_for_updates = false\n')
for kind in ['memory','progress']:
 panels=[]
 specs=[('VM A — 1 GiB limit','A'),('VM B — 4 GiB limit','B')]
 for i,(title,vm) in enumerate(specs):
  metrics=[('s3_live_bytes','App live allocations'),('s3_limit_bytes','Configured limit'),('s3_hami_memory_bytes','HAMi accounting')] if kind=='memory' else [('s3_completed_checks_total','Completed checks'),('s3_oom_total','Expected OOM count')]
  if kind=='progress':title='VM '+vm+' — synchronized and verified work / OOM'
  targets=[{'expr':metric+'{pair="$pair",vm="'+vm+'"}','refId':chr(65+j),'legendFormat':label} for j,(metric,label) in enumerate(metrics)]
  panels.append({'id':i+1,'type':'timeseries','title':title,'datasource':{'type':'prometheus','uid':'stage3-prom'},'gridPos':{'x':i*12,'y':0,'w':12,'h':14},'targets':targets,'fieldConfig':{'defaults':{'unit':'bytes' if kind=='memory' else 'short','min':0,'custom':{'lineWidth':2,'spanNulls':False}},'overrides':[]},'options':{'legend':{'displayMode':'table','placement':'bottom','calcs':['lastNotNull']}}})
  if kind=='memory':panels[-1]['fieldConfig']['overrides']=[{'matcher':{'id':'byName','options':'Configured limit'},'properties':[{'id':'custom.lineStyle','value':{'fill':'dash','dash':[8,8]}},{'id':'color','value':{'mode':'fixed','fixedColor':'red'}}]}]
 extra=[('Physical GPU memory — includes contexts and both Workers','s3_gpu_total_memory_bytes','bytes'),('Collector errors / scrape health','s3_collector_errors','short')] if kind=='memory' else [('Verified mismatches — must stay zero','s3_mismatches_total{pair="$pair"}','short'),('Scrape health — must stay 1','up{job="stage3"}','short')]
 for j,(title,expr,unit) in enumerate(extra):panels.append({'id':j+3,'type':'timeseries','title':title,'datasource':{'type':'prometheus','uid':'stage3-prom'},'gridPos':{'x':12*j,'y':14,'w':12,'h':8},'targets':[{'expr':expr,'refId':'A','legendFormat':'{{vm}}'}],'fieldConfig':{'defaults':{'unit':unit,'min':0,'custom':{'spanNulls':False}},'overrides':[]}})
 d={'uid':'stage3-'+kind,'title':'Stage 3 — '+kind+' — actual measurements','schemaVersion':40,'version':1,'timezone':'utc','refresh':'','time':{'from':'now-5m','to':'now'},'templating':{'list':[{'name':'pair','label':'Run pair','type':'custom','query':'pair-1,pair-2,pair-3','current':{'text':'pair-1','value':'pair-1'},'options':[{'text':'pair-'+str(n),'value':'pair-'+str(n),'selected':n==1} for n in range(1,4)]}]},'panels':panels,'annotations':{'list':[{'name':'Observed phase events','type':'dashboard','datasource':{'type':'grafana','uid':'-- Grafana --'},'enable':True,'hide':False,'iconColor':'rgba(255,180,60,1)','target':{'type':'tags','tags':['stage3','$pair'],'matchAny':False,'limit':100}}]}}
 (m/'dashboards'/('stage3-'+kind+'.json')).write_text(json.dumps(d,indent=2)+'\n')
password=secrets.token_urlsafe(24);auth=base/'grafana-auth.json';auth.write_text(json.dumps({'user':'admin','password':password}));auth.chmod(0o600)
tools=Path('.local/campaign-20260928/tools').resolve();processes=[]
commands=[('exporter',['python3','experiments/evidence/stage3_monitor.py','--output','experiments/evidence/results/2026-09-29-stage3','--observations',str(base/'observations.jsonl')],{}),('prometheus',[str(tools/'prometheus-3.5.0.linux-amd64/prometheus'),'--config.file='+str(m/'prometheus.yml'),'--storage.tsdb.path='+str(m/'prom-data'),'--web.listen-address=127.0.0.1:9098'],{}),('grafana',[str(tools/'grafana-v12.0.2/bin/grafana'),'server','--homepath',str(tools/'grafana-v12.0.2'),'--config',str(m/'grafana.ini')],{'GF_SECURITY_ADMIN_PASSWORD':password})]
for name,cmd,env in commands:
 f=(base/(name+'.txt')).open('w');proc=subprocess.Popen(cmd,stdout=f,stderr=f,env={**os.environ,**env},start_new_session=True);processes.append({'name':name,'pid':proc.pid,'command':cmd})
(base/'monitor-processes.json').write_text(json.dumps(processes,indent=2))
print('Started localhost metrics :9898, Prometheus :9098, Grafana :3301')
