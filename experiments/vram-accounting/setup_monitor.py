import json,subprocess,os,secrets
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];B=ROOT/'.local/vram-accounting-20261016';T=ROOT/'.local/campaign-20260928/tools'
for d in ['grafana-data','provisioning/datasources','provisioning/dashboards','dashboards']:(B/d).mkdir(parents=True,exist_ok=True)
(B/'prometheus.yml').write_text('global:\n  scrape_interval: 1s\nscrape_configs:\n  - job_name: vram\n    static_configs:\n      - targets: ["127.0.0.1:19896"]\n')
(B/'provisioning/datasources/prom.yaml').write_text('apiVersion: 1\ndatasources:\n  - name: VRAM Prometheus\n    uid: vram-prom\n    type: prometheus\n    access: proxy\n    url: http://127.0.0.1:19096\n    isDefault: true\n    jsonData:\n      timeInterval: 1s\n')
(B/'provisioning/dashboards/main.yaml').write_text('apiVersion: 1\nproviders:\n  - name: VRAM\n    type: file\n    options:\n      path: '+str(B/'dashboards')+'\n')
(B/'grafana.ini').write_text('[server]\nhttp_addr = 127.0.0.1\nhttp_port = 13096\n[paths]\ndata = '+str(B/'grafana-data')+'\nlogs = '+str(B/'grafana-data')+'\nprovisioning = '+str(B/'provisioning')+'\n[auth.anonymous]\nenabled = true\norg_role = Viewer\n[analytics]\nreporting_enabled = false\ncheck_for_updates = false\n')
queries=[('GPU physical memory (NVML, MiB resolution)','vram_device_used_bytes','bytes'),('HAMi accounted memory per Worker','hami_container_device_memory_bytes{pod=~"vram-.*"}','bytes'),('Application live requested bytes','vram_live_requested_bytes','bytes'),('Guest reported free bytes','vram_free_bytes','bytes'),('GPU utilization','vram_device_util_pct','percent'),('Guest reported quota total','vram_total_bytes','bytes')]
panels=[]
for i,(title,q,unit) in enumerate(queries):panels.append({'id':i+1,'title':title,'type':'timeseries','gridPos':{'x':i%2*12,'y':i//2*9,'w':12,'h':9},'datasource':{'type':'prometheus','uid':'vram-prom'},'targets':[{'refId':'A','expr':q,'legendFormat':'{{run}} {{pod}}'}],'fieldConfig':{'defaults':{'unit':unit},'overrides':[]}})
d={'uid':'vmweave-vram-20261016','title':'VMWeave VRAM boundary and accounting — 2026-10-16','schemaVersion':41,'version':1,'timezone':'Asia/Seoul','refresh':'5s','panels':panels,'time':{'from':'now-30m','to':'now'}}
saved_dashboard=ROOT/'experiments/vram-accounting/dashboard.json'
if saved_dashboard.exists():d=json.loads(saved_dashboard.read_text())
(B/'dashboards/vram.json').write_text(json.dumps(d,indent=2));(ROOT/'experiments/vram-accounting/dashboard.json').write_text(json.dumps(d,indent=2))
commands=[['python3',str(Path(__file__).with_name('monitor.py'))],[str(T/'prometheus-3.5.0.linux-amd64/prometheus'),'--config.file='+str(B/'prometheus.yml'),'--storage.tsdb.path='+str(B/'prom-data'),'--web.listen-address=127.0.0.1:19096','--storage.tsdb.retention.time=30d'],[str(T/'grafana-v12.0.2/bin/grafana'),'server','--homepath',str(T/'grafana-v12.0.2'),'--config',str(B/'grafana.ini')]]
pids=[]
for i,cmd in enumerate(commands):
 env=os.environ.copy()
 if i==2:env['GF_SECURITY_ADMIN_PASSWORD']=secrets.token_urlsafe(32)
 with (B/f'service-{i}.log').open('w') as f:p=subprocess.Popen(cmd,stdout=f,stderr=f,env=env,start_new_session=True);pids.append(p.pid)
(B/'monitor-pids.json').write_text(json.dumps(pids));print('Monitoring services started',pids)
