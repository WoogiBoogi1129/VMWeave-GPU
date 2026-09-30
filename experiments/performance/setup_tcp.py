import json,pathlib,secrets,sys,time
from common import *
def k(args, **kw):return call(['kubectl',*args],**kw)
b=BASE;cfg=b/'legacy-config';cfg.mkdir(exist_ok=True)
password=secrets.token_urlsafe(24);save(BASE/'legacy-auth.json',{'password':password});(BASE/'legacy-auth.json').chmod(0o600)
(cfg/'cluster-mgr.toml').write_text(f'''[vm-resource-db]
host="127.0.0.1"
port=27017
user="perf"
password="{password}"
dbname="flyt"
[ports]
node=12401
client=12402
[virt-server-auto-deallocate]
enabled=false
grace-period=60
[ipc]
mqueue-path="/tmp/flyt-rmgr-queue"
frontend-socket="/tmp/flyt-frontend-socket"
[migration]
ckp-path="/tmp/flytckp"
[metrics]
port=12403
interval=30
''');(cfg/'cluster-mgr.toml').chmod(0o600)
images=json.loads((BASE/'images.json').read_text());manager=images['manager'];cell=images['cell']
pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':'perf-tcp-manager','namespace':NS},'spec':{'nodeName':'gpu-4','restartPolicy':'Never','automountServiceAccountToken':False,'containers':[{'name':'manager','image':manager,'command':['/bin/sh','-c','sleep 15; exec /opt/flyt/bin/flyt-cluster-manager'],'env':[{'name':'RUST_LOG','value':'info'}],'securityContext':{'runAsUser':0},'volumeMounts':[{'name':'cfg','mountPath':'/etc/flyt','readOnly':True}]},{'name':'mongo','image':'docker.io/library/mongo:7.0','env':[{'name':'MONGO_INITDB_ROOT_USERNAME','value':'perf'},{'name':'MONGO_INITDB_ROOT_PASSWORD','value':password}]}],'volumes':[{'name':'cfg','hostPath':{'path':str(cfg),'type':'Directory'}}]}}
x=json.loads(k(['create','-f','-','-o','json'],input=json.dumps(pod),private=True));save(b/'private-manager.json',x)
wait(lambda:get('pod',x['metadata']['name']).get('status',{}).get('phase')=='Running',600)
ip=get('pod',x['metadata']['name'])['status']['podIP']
(cfg/'node-mgr.toml').write_text(f'''[resource-manager]
address="{ip}"
port=12401
[virt-server]
program-path="/opt/flyt/bin/cricket-rpc-server"
thread-mode=0
program-args=""
[ipc]
mqueue-path="/tmp/flyt-servernode-queue"
''')
(cfg/'client-mgr.toml').write_text(f'''[resource-manager]
address="{ip}"
port=12402
metrics-port=12403
[vcuda-client]
process_monitor_period=1
[ipc]
mqueue-path="/tmp/flyt-client-mgr"
[resource-metrics]
scaleup-factor=60
scaledown-factor=60
metric-interval=3
log-file="/tmp/flyt_shmem.log"
''')
save(b/'legacy.json',{'manager_ip':ip,'manager_uid':x['metadata']['uid'],'cell_image':cell})
print('legacy manager running',ip,flush=True)
