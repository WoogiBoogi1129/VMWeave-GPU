import json,subprocess,time
from pathlib import Path
R=Path.cwd();B=R/'.local/rodinia-steady-20261026';O=R/'experiments/ai-passthrough/results/20261026-rodinia-steady';s=json.loads((B/'state.json').read_text());NS=s['namespace'];ADMIN='rodinia-admin-1026'
def k(*a,**kw):return subprocess.check_output(['kubectl',*map(str,a)],text=True,**kw)
def get(kind,name):
 x=k('get',kind,name,'-n',NS,'--ignore-not-found','-o','json');return json.loads(x) if x.strip() else None
v=get('vm',s['name'])
if v:
 assert v['metadata']['uid']==s['vmUID']
 k('delete','vm',s['name'],'-n',NS,'--wait=true','--timeout=180s')
end=time.monotonic()+180
while get('vmi',s['name']) and time.monotonic()<end:time.sleep(2)
assert not get('vmi',s['name'])
k('delete','pod','flyt-server','-n',NS,'--ignore-not-found','--wait=true','--timeout=120s')
k('delete','pvc','shm','-n',NS,'--ignore-not-found','--wait=true','--timeout=120s')
k('delete','pv','rodinia-flyt-shm-1026','--ignore-not-found','--wait=true','--timeout=120s')
if not get('pod',ADMIN):
 im=json.loads((R/'deploy/releases/v0.5.3.json').read_text())['images']['worker'];p={'apiVersion':'v1','kind':'Pod','metadata':{'name':ADMIN,'namespace':NS},'spec':{'nodeName':'gpu-4','terminationGracePeriodSeconds':1,'restartPolicy':'Never','automountServiceAccountToken':False,'containers':[{'name':'admin','image':im,'command':['sleep','600'],'securityContext':{'privileged':True,'runAsUser':0},'volumeMounts':[{'name':'host','mountPath':'/host'}]}],'volumes':[{'name':'host','hostPath':{'path':'/','type':'Directory'}}]}};k('create','-f','-',input=json.dumps(p))
k('wait','-n',NS,'--for=condition=Ready','pod/'+ADMIN,'--timeout=120s')
assert s['directory']=='/var/lib/vmweave/rodinia-steady-20261026/flyt'
k('exec','-n',NS,ADMIN,'--','chroot','/host','rm','-rf',s['directory'])
k('delete','pod',ADMIN,'-n',NS,'--wait=true','--timeout=120s')
k('delete','namespace',NS,'--wait=true','--timeout=120s')
prod=json.loads(k('get','sharedmemorychannel','vmweave-k8s-01','-n','vmweave-test-a','-o','json'));assert prod['status']['phase']=='Ready'
gpu=subprocess.check_output(['nvidia-smi','-i','GPU-772181af-05a4-0c24-de59-8487bd37c142','--query-gpu=uuid,memory.used','--format=csv,noheader'],text=True)
(O/'cleanup.json').write_text(json.dumps({'testNamespaceRemoved':True,'testVMAndPVCPVRemoved':True,'testBackingRemoved':True,'productionChannelPhase':prod['status']['phase'],'gpu0':gpu.strip(),'pciRebindPerformed':False},indent=2));print('Test cleanup complete; production Ready')
