import pathlib,subprocess,json,time,sys
sys.path.insert(0,'.local/device-plugin-20261105');import lab
R=pathlib.Path('experiments/cnn-model/results/20261113');L=pathlib.Path('.local/cnn-model-20261113');image=json.loads((R/'candidate-artifact-identity.json').read_text())['workerImage']
for attempt in range(150):
 c=json.loads(subprocess.check_output(['kubectl','-n','vmweave-test-b','get','sharedmemorychannel','dp-dev-20261105','-o','json']))
 if c['status']['phase']=='Ready' and c['spec']['workerImage']==image:
  try:
   if lab.ssh('kubectl get --raw=/readyz',check=False).stdout.strip()=='ok':break
  except Exception:pass
 time.sleep(2)
else:raise TimeoutError('candidate readiness')
for name,case in [('relu','relu'),('pool','pool'),('cnn','cnn'),('cnn-repeat','cnn'),('mnist','mnist')]:
 result=subprocess.run(['python3','experiments/cnn-model/runner/run.py','run','--connection',str(L/'connection.json'),'--results',str(R),'--name','candidate-'+name,'--backend','legacy','--case',case,'--guest-library','.local/cnn-training-20261113/build/libvmweave_guest.so','--worker-image',image])
 (R/('candidate-'+name+'-worker.log')).write_bytes(subprocess.check_output(['kubectl','-n','vmweave-test-b','logs',c['status']['resourcePrefix']+'-worker','--all-containers=true']))
 if result.returncode:raise SystemExit(result.returncode)
