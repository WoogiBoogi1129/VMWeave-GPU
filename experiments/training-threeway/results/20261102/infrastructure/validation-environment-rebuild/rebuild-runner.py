import sys,subprocess,json,time,shutil
from pathlib import Path
sys.path.insert(0,'experiments/training-threeway')
from lab import *
from backends import idle
idle()
assert not get('namespace',NS)
d=O/'infrastructure/validation-environment-rebuild';d.mkdir(exist_ok=False)
shutil.copyfile(O/'cleanup.json',d/'interim-cleanup.json')
shutil.copyfile(B/'finalize-retry.log',d/'retry-dispatch-failure.txt')
save(d/'decision.json',{'utc':time.time(),'reason':'Retry dispatcher hit existing host-context directory; its safety handler cleaned up test resources before supplementary checks. Rebuild only validation VMs from the same frozen source artifacts; do not rerun or modify the completed 300 performance measurements.','cause':'orchestration error','planned_checks':24})
create({'apiVersion':'v1','kind':'Namespace','metadata':{'name':NS,'labels':{'experiment':'training-threeway-20261102'}}})
create(json.loads((B/'admin.json').read_text()))
wait(lambda:(x:=get('pod','admin')) and x.get('status',{}).get('phase')=='Running')
original=json.loads((B/'hami-config-before.json').read_text())['data']['config.json']
assert get('cm','hami-device-plugin','kube-system')['data']['config.json']==original
cfg=json.loads(original);next(x for x in cfg['nodeconfig'] if x['name']=='gpu-4')['filterdevices']['uuid'].remove(GPU)
patch('cm','hami-device-plugin',{'data':{'config.json':json.dumps(cfg)}},'kube-system')
k('rollout','restart','ds/hami-device-plugin','-n','kube-system');k('rollout','status','ds/hami-device-plugin','-n','kube-system','--timeout=120s')
for command in [['python3','-u','experiments/training-threeway/lab.py','base'],['python3','-u','experiments/training-threeway/prepare.py']]:
 print('START',command,time.time(),flush=True);subprocess.run(command,check=True)
print('VALIDATION_ENVIRONMENT_REBUILT',flush=True)
subprocess.run(['python3','-u','experiments/training-threeway/check_transfers.py','--reuse-host-context'],check=True)
from cleanup import cleanup
cleanup()
subprocess.run(['.local/evidence-venv/bin/python','experiments/training-threeway/analyze.py','--plots'],check=True)
subprocess.run(['python3','experiments/training-threeway/report.py'],check=True)
from validate import validate
save(O/'audit.json',validate(O))
save(B/'postprocess-complete.json',{'utc':time.time(),'passed':True})
print('POSTPROCESS_COMPLETE',flush=True)
