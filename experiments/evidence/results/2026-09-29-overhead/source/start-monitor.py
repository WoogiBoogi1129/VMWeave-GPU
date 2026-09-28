from pathlib import Path
import json,os,secrets,subprocess
b=Path('.local/overhead-20260929').resolve();m=b/'monitoring';m.mkdir(exist_ok=True)
for sub in ['provisioning/datasources','provisioning/dashboards','dashboards','grafana-data','grafana-logs']:(m/sub).mkdir(parents=True,exist_ok=True)
(m/'prometheus.yml').write_text('global:\n  scrape_interval: 1s\n  scrape_timeout: 900ms\nscrape_configs:\n  - job_name: overhead\n    static_configs:\n      - targets: ["127.0.0.1:9898"]\n')
(m/'provisioning/datasources/prometheus.yaml').write_text('apiVersion: 1\ndatasources:\n  - name: Overhead Prometheus\n    uid: perf-prom\n    type: prometheus\n    access: proxy\n    url: http://127.0.0.1:9098\n    isDefault: true\n    jsonData:\n      timeInterval: 1s\n')
(m/'provisioning/dashboards/perf.yaml').write_text('apiVersion: 1\nproviders:\n  - name: Overhead\n    type: file\n    options:\n      path: '+str(m/'dashboards')+'\n')
(m/'grafana.ini').write_text(f'[server]\nhttp_addr = 127.0.0.1\nhttp_port = 3301\n[paths]\ndata = {m}/grafana-data\nlogs = {m}/grafana-logs\nprovisioning = {m}/provisioning\n[auth.anonymous]\nenabled = true\norg_role = Viewer\n[analytics]\nreporting_enabled = false\ncheck_for_updates = false\n')
specs=[('GPU utilization (whole GPU)','perf_gpu_util_percent','percent'),('CPU cores used (exclusive Pod cgroups)','rate(perf_pod_cpu_seconds_total[10s])','short'),('GPU memory (includes contexts)','perf_gpu_memory_mib','mbytes'),('GPU SM clock','perf_gpu_sm_clock_mhz','suffix:MHz'),('GPU temperature','perf_gpu_temperature_c','celsius'),('Collector errors','perf_collector_errors','short')]
panels=[]
for i,(title,expr,unit) in enumerate(specs):panels.append({'id':i+1,'type':'timeseries','title':title,'datasource':{'type':'prometheus','uid':'perf-prom'},'gridPos':{'x':12*(i%2),'y':8*(i//2),'w':12,'h':8},'targets':[{'expr':expr,'refId':'A','legendFormat':'{{session}} {{role}}'}],'fieldConfig':{'defaults':{'unit':unit,'min':0,'custom':{'spanNulls':False}},'overrides':[]}})
d={'uid':'overhead','title':'N / Flyt TCP / Proposed SHM — actual monitoring','schemaVersion':40,'version':1,'timezone':'utc','refresh':'','panels':panels,'annotations':{'list':[{'name':'Measured windows','type':'dashboard','datasource':{'type':'grafana','uid':'-- Grafana --'},'enable':True,'iconColor':'orange','target':{'type':'tags','tags':['overhead'],'limit':1000}}]}}
(m/'dashboards/overhead.json').write_text(json.dumps(d,indent=2))
password=secrets.token_urlsafe(24);(b/'grafana-auth.json').write_text(json.dumps({'user':'admin','password':password}));(b/'grafana-auth.json').chmod(0o600)
t=Path('.local/campaign-20260928/tools').resolve();commands=[('cpu',['python3','experiments/evidence/overhead_cpu.py',str(b/'state.json')],{}),('exporter',['python3','experiments/evidence/overhead_monitor.py',str(b)],{}),('prometheus',[str(t/'prometheus-3.5.0.linux-amd64/prometheus'),'--config.file='+str(m/'prometheus.yml'),'--storage.tsdb.path='+str(m/'prom-data'),'--web.listen-address=127.0.0.1:9098'],{}),('grafana',[str(t/'grafana-v12.0.2/bin/grafana'),'server','--homepath',str(t/'grafana-v12.0.2'),'--config',str(m/'grafana.ini')],{'GF_SECURITY_ADMIN_PASSWORD':password})]
pids=[]
for name,cmd,env in commands:
 out=(b/('cpu.jsonl' if name=='cpu' else name+'.log')).open('w');pr=subprocess.Popen(['taskset','-c','48-51',*cmd],stdout=out,stderr=(b/(name+'.stderr')).open('w'),env={**os.environ,**env},start_new_session=True);pids.append({'name':name,'pid':pr.pid,'command':cmd})
(b/'monitor-processes.json').write_text(json.dumps(pids,indent=2));print('Started Prometheus/Grafana, GPU and exclusive Pod CPU counters at 1 s.')
