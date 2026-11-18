from infra import *
import secrets
CELL='localhost/flyt-gpu-cell@sha256:0b21e0df1222f5861b522994a80416e243870663372d3cd2a886d36a221efbbd'
MANAGER='localhost/flyt-cluster-manager@sha256:7789348f62da6f2d9fa1ee031d323be1cf7f6e1b44c563d104745e0deca9a0b8'
def start_manager():
 cfg=B/'flyt-config';cfg.mkdir(exist_ok=True,mode=0o700)
 password=secrets.token_urlsafe(24)
 (cfg/'cluster-mgr.toml').write_text(f'''[vm-resource-db]
host="127.0.0.1"
port=27017
user="comm"
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
 p={'apiVersion':'v1','kind':'Pod','metadata':{'name':'flyt-manager','namespace':NS},'spec':{'nodeSelector':{'kubernetes.io/hostname':NODE},'restartPolicy':'Never','automountServiceAccountToken':False,'containers':[{'name':'manager','image':MANAGER,'imagePullPolicy':'Never','command':['/bin/sh','-c','sleep 12; exec /opt/flyt/bin/flyt-cluster-manager'],'env':[{'name':'RUST_LOG','value':'info'}],'resources':{'limits':{'cpu':'1','memory':'1Gi'}},'securityContext':{'runAsUser':0},'volumeMounts':[{'name':'cfg','mountPath':'/etc/flyt','readOnly':True}]},{'name':'mongo','image':'docker.io/library/mongo@sha256:c53852c00c23ca9f23fc39690350ffa9a80e3642fe8f96879726d8da0abe80a7','env':[{'name':'MONGO_INITDB_ROOT_USERNAME','value':'comm'},{'name':'MONGO_INITDB_ROOT_PASSWORD','value':password}],'resources':{'limits':{'cpu':'1','memory':'2Gi'}}}],'volumes':[{'name':'cfg','hostPath':{'path':str(cfg),'type':'Directory'}}]}}
 create(p);wait(lambda:get('pod','flyt-manager').get('status',{}).get('phase')=='Running',180)
 ip=get('pod','flyt-manager')['status']['podIP']
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
 time.sleep(15)
 return ip

def start_server():
 mounts=[{'name':'cfg','mountPath':'/etc/flyt','readOnly':True},{'name':'mps','mountPath':'/run/flyt-mps'},{'name':'mps-log','mountPath':'/var/log/flyt-mps'},{'name':'shm','mountPath':'/dev/shm'}]
 volumes=[{'name':'cfg','hostPath':{'path':str(B/'flyt-config'),'type':'Directory'}},{'name':'mps','emptyDir':{}},{'name':'mps-log','emptyDir':{}},{'name':'shm','emptyDir':{'medium':'Memory','sizeLimit':'2Gi'}}]
 p=gpu_pod('flyt-server',CELL,['taskset','-c','12-15','/usr/local/bin/flyt-gpu-cell-entrypoint'],{'FLYT_ALLOWED_GPU_UUIDS':GPU,'FLYT_NODE_MANAGER_CONFIG':'/etc/flyt/node-mgr.toml','RUST_LOG':'info'},mounts,volumes)
 return p

def connect(s,p):
 seed='const c=db.getSiblingDB("flyt").vm_required_resources;c.updateOne({vm_ip:'+json.dumps(s['ip'])+'},{$set:{vm_ip:'+json.dumps(s['ip'])+',host_ip:'+json.dumps(p['status']['podIP'])+',compute_units:188,memory:97887}},{upsert:true});printjson(c.findOne({vm_ip:'+json.dumps(s['ip'])+'},{_id:0}));'
 result=k('exec','-n',NS,'flyt-manager','-c','mongo','--','/bin/sh','-c','exec mongosh --quiet --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --eval "$1"','sh',seed)
 copy(s,[B/'flyt-config/client-mgr.toml'],'/tmp/comm/')
 remote(s,'sudo mkdir -p /etc/flyt; sudo cp /tmp/comm/client-mgr.toml /etc/flyt/client-mgr.toml; sudo sh -c "nohup env LD_LIBRARY_PATH=/opt/comm/artifacts/F RUST_LOG=info /opt/comm/artifacts/F/flyt-client-manager >/tmp/comm/flyt-manager.log 2>&1 </dev/null &"')
 time.sleep(3)
 return result
