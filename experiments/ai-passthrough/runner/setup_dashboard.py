"""Local-only dashboard with a dedicated Prometheus scrape of trial metrics."""
import json,subprocess,os,secrets
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];B=ROOT/'.local/ai-passthrough-20261016';T=ROOT/'.local/campaign-20260928/tools'
for d in ['grafana-data','provisioning/datasources','provisioning/dashboards','dashboards']:(B/d).mkdir(parents=True,exist_ok=True)
(B/'prometheus.yml').write_text('global:\n  scrape_interval: 1s\nscrape_configs:\n  - job_name: ai_perf\n    static_configs:\n      - targets: ["127.0.0.1:19898"]\n')
(B/'provisioning/datasources/prom.yaml').write_text('apiVersion: 1\ndatasources:\n  - name: AI performance Prometheus\n    uid: ai-perf-prom\n    type: prometheus\n    access: proxy\n    url: http://127.0.0.1:19098\n    isDefault: true\n    jsonData:\n      timeInterval: 1s\n')
(B/'provisioning/dashboards/main.yaml').write_text('apiVersion: 1\nproviders:\n  - name: AI performance\n    type: file\n    options:\n      path: '+str(B/'dashboards')+'\n')
(B/'grafana.ini').write_text('[server]\nhttp_addr = 127.0.0.1\nhttp_port = 13098\n[paths]\ndata = '+str(B/'grafana-data')+'\nlogs = '+str(B/'grafana-data')+'\nprovisioning = '+str(B/'provisioning')+'\n[auth.anonymous]\nenabled = true\norg_role = Viewer\n[analytics]\nreporting_enabled = false\ncheck_for_updates = false\n')
queries=[('GPU utilization','ai_gpu_utilization','percent'),('Completed training throughput (samples/s)','ai_throughput','none'),('Device memory (MiB)','ai_gpu_memory_MiB','none'),('GPU power (W)','ai_gpu_power_W','watt'),('SM clock (MHz)','ai_gpu_clock_MHz','none'),('Temperature','ai_gpu_temperature_C','celsius')]
panels=[]
for i,(title,q,unit) in enumerate(queries):
 panels.append({'id':i+1,'title':title,'type':'timeseries','gridPos':{'x':i%2*12,'y':i//2*10,'w':12,'h':10},'datasource':{'type':'prometheus','uid':'ai-perf-prom'},'targets':[{'refId':'A','expr':q+'{run=~"$run",condition=~"$condition"}','legendFormat':'{{run}} / {{condition}}'}],'fieldConfig':{'defaults':{'unit':unit,'min':0},'overrides':[]}})
panels[0]['fieldConfig']['defaults']['max']=100
d={'uid':'vmweave-ai-perf-20261016','title':'VMWeave vs GPU passthrough: FP32 AI training — 2026-10-16','schemaVersion':41,'version':1,'timezone':'Asia/Seoul','templating':{'list':[{'name':'run','type':'textbox','label':'Run regex','current':{'text':'.*','value':'.*'},'query':'.*'},{'name':'condition','type':'textbox','label':'Condition regex','current':{'text':'.*','value':'.*'},'query':'.*'}]},'refresh':'5s','panels':panels,'time':{'from':'now-15m','to':'now'}}
(B/'dashboards/pair.json').write_text(json.dumps(d,indent=2));(ROOT/'experiments/ai-passthrough/dashboard.json').write_text(json.dumps(d,indent=2)+'\n')
commands=[['prometheus',str(T/'prometheus-3.5.0.linux-amd64/prometheus'),'--config.file='+str(B/'prometheus.yml'),'--storage.tsdb.path='+str(B/'prom-data'),'--web.listen-address=127.0.0.1:19098','--storage.tsdb.retention.time=30d'],['grafana',str(T/'grafana-v12.0.2/bin/grafana'),'server','--homepath',str(T/'grafana-v12.0.2'),'--config',str(B/'grafana.ini')]]
pids={}
for name,*cmd in commands:
 env=os.environ.copy()
 if name=='grafana':env['GF_SECURITY_ADMIN_PASSWORD']=secrets.token_urlsafe(32)
 with (B/(name+'.log')).open('w') as f:p=subprocess.Popen(cmd,stdout=f,stderr=f,env=env,start_new_session=True);pids[name]=p.pid
(B/'dashboard-pids.json').write_text(json.dumps(pids));print('Dashboard processes:',pids)
