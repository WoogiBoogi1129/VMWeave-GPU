import json,subprocess,time
from pathlib import Path
out=Path('experiments/evidence/results/2026-09-28-stage2-static')
def k(*args,**kwargs):return subprocess.check_output(['kubectl',*args],text=True,**kwargs)
name='evidence-s2-static-audit'
image=json.loads((out/'protocol.json').read_text())['worker_image']
pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':'flyt-evidence'},'spec':{'nodeName':'gpu-4','restartPolicy':'Never','activeDeadlineSeconds':120,'automountServiceAccountToken':False,'securityContext':{'runAsUser':107,'runAsGroup':107},'containers':[{'name':'audit','image':image,'command':['python3','-c','import os,json; x=os.listdir("/audit"); print(json.dumps({"pvc":"evidence-vm-a-backing","entries":x,"empty":not x})); raise SystemExit(bool(x))'],'securityContext':{'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}},'volumeMounts':[{'name':'backing','mountPath':'/audit','readOnly':True}]}],'volumes':[{'name':'backing','persistentVolumeClaim':{'claimName':'evidence-vm-a-backing','readOnly':True}}]}}
created=json.loads(k('create','-f','-','-o','json',input=json.dumps(pod)))
try:
 end=time.monotonic()+120
 while time.monotonic()<end:
  actual=json.loads(k('get','pod',name,'-n','flyt-evidence','-o','json'))
  if actual['status']['phase'] in ['Succeeded','Failed']:break
  time.sleep(1)
 result=json.loads(k('logs',name,'-n','flyt-evidence'))
 assert actual['status']['phase']=='Succeeded' and result['empty']
 result.update(pod_uid=created['metadata']['uid'],observed_utc=time.time(),read_only=True)
finally:
 actual=json.loads(k('get','pod',name,'-n','flyt-evidence','-o','json'))
 assert actual['metadata']['uid']==created['metadata']['uid']
 k('delete','pod',name,'-n','flyt-evidence','--wait=true','--timeout=60s')
result['audit_pod_deleted']=True
(out/'backing-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
