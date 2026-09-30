"""Dedicated Kubernetes Prometheus/Grafana; existing DCGM is preserved."""
import json, secrets
from common import *

ensure_admin()
M=BASE/'monitoring';M.mkdir(exist_ok=True)
MON='vmweave-performance'
if not get('namespace',MON,ns='default'):create({'apiVersion':'v1','kind':'Namespace','metadata':{'name':MON}})
tools=ROOT/'.local/campaign-20260928/tools'
for sub in ['prom-data','grafana-data','provisioning/datasources','provisioning/dashboards','dashboards']:(M/sub).mkdir(parents=True,exist_ok=True)

# Match the currently installed exporter; separate instance has a one-second watch.
dcgm={'apiVersion':'v1','kind':'Pod','metadata':{'name':'perf-dcgm','namespace':MON},'spec':{'nodeName':'gpu-4','runtimeClassName':'nvidia','restartPolicy':'Always','automountServiceAccountToken':False,
 'containers':[{'name':'dcgm','image':'nvcr.io/nvidia/k8s/dcgm-exporter:4.6.0-4.8.3-distroless','args':['-c','1000'],
 'env':[{'name':'NVIDIA_VISIBLE_DEVICES','value':'k8s.device-plugin.nvidia.com/gpu='+GPU},{'name':'NVIDIA_DRIVER_CAPABILITIES','value':'compute,utility'},{'name':'DCGM_EXPORTER_KUBERNETES','value':'false'}],
 'securityContext':{'capabilities':{'add':['SYS_ADMIN']}},'ports':[{'containerPort':9400}]}]}}
if not get('pod','perf-dcgm',MON):create(dcgm)
wait(lambda:get('pod','perf-dcgm',MON).get('status',{}).get('phase')=='Running')
dip=get('pod','perf-dcgm',MON)['status']['podIP']
node={'apiVersion':'v1','kind':'Pod','metadata':{'name':'perf-node-exporter','namespace':MON},'spec':{'nodeName':'gpu-4','hostPID':True,'restartPolicy':'Always','automountServiceAccountToken':False,'containers':[{'name':'node-exporter','image':'quay.io/prometheus/node-exporter:v1.9.1','args':['--path.rootfs=/host','--path.procfs=/host/proc','--path.sysfs=/host/sys','--collector.filesystem.mount-points-exclude=^/(dev|proc|sys|var/lib/containers|var/lib/kubelet)($|/)'],'volumeMounts':[{'name':'host','mountPath':'/host','readOnly':True}]}],'volumes':[{'name':'host','hostPath':{'path':'/','type':'Directory'}}]}}
if not get('pod','perf-node-exporter',MON):create(node)
wait(lambda:get('pod','perf-node-exporter',MON).get('status',{}).get('phase')=='Running')
nip=get('pod','perf-node-exporter',MON)['status']['podIP']
(M/'prometheus.yml').write_text('global:\n  scrape_interval: 1s\n  scrape_timeout: 900ms\nscrape_configs:\n  - job_name: dcgm\n    static_configs:\n      - targets: ["'+dip+':9400"]\n  - job_name: experiment\n    static_configs:\n      - targets: ["192.168.24.21:9899"]\n  - job_name: hami\n    static_configs:\n      - targets: ["hami-device-plugin-monitor.kube-system.svc:31992"]\n  - job_name: node\n    static_configs:\n      - targets: ["'+nip+':9100"]\n')
(M/'provisioning/datasources/prometheus.yaml').write_text('apiVersion: 1\ndatasources:\n  - name: Performance Prometheus\n    uid: perf-prom\n    type: prometheus\n    access: proxy\n    url: http://127.0.0.1:9090\n    isDefault: true\n    jsonData:\n      timeInterval: 1s\n')
(M/'provisioning/dashboards/perf.yaml').write_text('apiVersion: 1\nproviders:\n  - name: Performance\n    type: file\n    options:\n      path: /monitor/dashboards\n')
(M/'grafana.ini').write_text('[server]\nhttp_port = 3000\n[paths]\ndata = /monitor/grafana-data\nlogs = /monitor/grafana-data\nprovisioning = /monitor/provisioning\n[auth.anonymous]\nenabled = true\norg_role = Viewer\n[analytics]\nreporting_enabled = false\ncheck_for_updates = false\n')
specs=[('GPU utilization — whole device','DCGM_FI_DEV_GPU_UTIL','percent'),('Completed operations per second','rate(vmweave_completed_total[5s])','ops'),('Application phase','vmweave_phase','short'),('GPU framebuffer used','DCGM_FI_DEV_FB_USED','mbytes'),('GPU power','DCGM_FI_DEV_POWER_USAGE','watt'),('GPU SM clock','DCGM_FI_DEV_SM_CLOCK','suffix:MHz'),('GPU temperature','DCGM_FI_DEV_GPU_TEMP','celsius'),('Requested HAMi cap','vmweave_compute_cap_percent','percent')]
panels=[]
for i,(title,expr,unit) in enumerate(specs):panels.append({'id':i+1,'type':'timeseries','title':title,'datasource':{'type':'prometheus','uid':'perf-prom'},'gridPos':{'x':12*(i%2),'y':7*(i//2),'w':12,'h':7},'targets':[{'expr':expr,'refId':'A','legendFormat':'{{run_id}} {{vm}} {{UUID}}'}],'fieldConfig':{'defaults':{'unit':unit,'min':0,'custom':{'spanNulls':False}},'overrides':[]}})
dashboard={'uid':'vmweave-performance','title':'VMWeave performance — actual observations','schemaVersion':40,'version':1,'timezone':'utc','refresh':'','panels':panels}
save(M/'dashboards/performance.json',dashboard)
password=json.loads((BASE/'grafana-auth.json').read_text())['password'] if (BASE/'grafana-auth.json').exists() else secrets.token_urlsafe(24)
save(BASE/'grafana-auth.json',{'user':'admin','password':password});(BASE/'grafana-auth.json').chmod(0o600)
if not get('secret','perf-grafana-auth',MON):
    create({'apiVersion':'v1','kind':'Secret','metadata':{'name':'perf-grafana-auth','namespace':MON},'stringData':{'password':password}},private=True)
pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':'perf-monitor','namespace':MON},'spec':{'nodeName':'gpu-4','restartPolicy':'Always','automountServiceAccountToken':False,'securityContext':{'runAsUser':0},
 'containers':[{'name':'prometheus','image':ADMIN,'command':['/tools/prometheus-3.5.0.linux-amd64/prometheus','--config.file=/monitor/prometheus.yml','--storage.tsdb.path=/monitor/prom-data','--storage.tsdb.retention.time=30d','--web.enable-admin-api'],
 'volumeMounts':[{'name':'tools','mountPath':'/tools','readOnly':True},{'name':'monitor','mountPath':'/monitor'}]},
 {'name':'grafana','image':ADMIN,'command':['/tools/grafana-v12.0.2/bin/grafana','server','--homepath','/tools/grafana-v12.0.2','--config','/monitor/grafana.ini'],
 'env':[{'name':'GF_SECURITY_ADMIN_PASSWORD','valueFrom':{'secretKeyRef':{'name':'perf-grafana-auth','key':'password'}}}],
 'volumeMounts':[{'name':'tools','mountPath':'/tools','readOnly':True},{'name':'monitor','mountPath':'/monitor'}]}],
 'volumes':[{'name':'tools','hostPath':{'path':str(tools),'type':'Directory'}},{'name':'monitor','hostPath':{'path':str(M),'type':'Directory'}}]}}
if not get('pod','perf-monitor',MON):create(pod,private=True)
wait(lambda:all(s.get('ready') for s in get('pod','perf-monitor',MON).get('status',{}).get('containerStatuses',[])) and len(get('pod','perf-monitor',MON).get('status',{}).get('containerStatuses',[]))==2)
ip=get('pod','perf-monitor',MON)['status']['podIP']
save(BASE/'monitor.json',{'prometheus':'http://'+ip+':9090','grafana':'http://'+ip+':3000','dcgm':'http://'+dip+':9400','namespace':MON})
save(OUT/'monitoring/setup.json',{'prometheus_version':'3.5.0','grafana_version':'12.0.2','dcgm_image':dcgm['spec']['containers'][0]['image'],'dcgm_collect_ms':1000,'scrape_seconds':1,'deployment':'Kubernetes Pods; dedicated hostPath data; existing exporter untouched'})
print('Monitoring endpoints saved; no credentials in public evidence.')
