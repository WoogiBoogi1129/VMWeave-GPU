import subprocess,time,json,pathlib,sys
sys.path.insert(0,'.local/device-plugin-20261105');import lab
R=pathlib.Path('experiments/cnn-training/results/20261113');L=pathlib.Path('.local/cnn-training-20261113')
image='localhost/vmweave-worker@'+(L/'worker-digest').read_text().strip()
for attempt in range(100):
 c=json.loads(subprocess.check_output(['kubectl','-n','vmweave-test-b','get','sharedmemorychannel','dp-dev-20261105','-o','json']))
 if c['status']['phase']=='Ready' and c['spec']['workerImage']==image:
  try:
   if lab.ssh('kubectl get --raw=/readyz',check=False).stdout.strip()=='ok':break
  except Exception:pass
 time.sleep(2)
else:raise TimeoutError('candidate readiness')
for name,case in [('input-v2','input-only'),('weight','weight-only'),('minimal','minimal'),('matrix','matrix'),('matrix-repeat','matrix'),('accumulate','accumulate')]:
 args=['python3','experiments/cnn-training/runner/run.py','run','--connection',str(L/'connection.json'),'--results',str(R),'--name','candidate-'+name,'--backend','legacy','--case',case,'--guest-library',str(L/'build/libvmweave_guest.so'),'--worker-image',image]
 result=subprocess.run(args)
 (R/('candidate-'+name+'-worker.log')).write_bytes(subprocess.check_output(['kubectl','-n','vmweave-test-b','logs',c['status']['resourcePrefix']+'-worker','--all-containers=true']))
 if result.returncode:raise SystemExit(result.returncode)
