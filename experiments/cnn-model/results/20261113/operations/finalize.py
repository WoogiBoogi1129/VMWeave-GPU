import pathlib,json,subprocess,time,sys
sys.path.insert(0,'.local/device-plugin-20261105');import lab
R=pathlib.Path('experiments/cnn-model/results/20261113');L=pathlib.Path('.local/cnn-model-20261113')
end=time.monotonic()+900
while not (R/'candidate-mnist-worker.log').exists():
 if time.monotonic()>end:raise TimeoutError('suite incomplete')
 time.sleep(2)
assert json.loads((R/'candidate-mnist/exit.json').read_text())['returncode']==0
cmd='export PYTHONPATH=/repo/.local/thesis-isolation-20261012/bundle-stage/opt/torch-venv/lib/python3.10/site-packages; export LD_LIBRARY_PATH=/repo/.local/thesis-isolation-20261012/bundle-stage/opt/flyt-cuda-libs:/usr/local/cuda/lib64; python3 experiments/cnn-model/audit_tensors.py'
with (R/'tensor-audit.log').open('w') as out:
 subprocess.run(['podman','run','--rm','--entrypoint','/bin/bash','-v',str(pathlib.Path.cwd())+':/repo','-w','/repo','localhost/vmweave-rnn-builder:validated','-ec',cmd],stdout=out,stderr=subprocess.STDOUT,check=True)
base=['python3','experiments/rnn-default/runner/run.py','--connection',str(L/'rnn-connection.json'),'--results',str(R/'regression')]
subprocess.run(base+['prepare'],check=True)
for attempt in range(60):
 if lab.ssh('kubectl -n rnn-default-model-20261113 get serviceaccount default --ignore-not-found -o name').stdout.strip():break
 time.sleep(1)
else:raise TimeoutError('default account')
subprocess.run(base+['run','--name','candidate-basic-after','--case','basic','--guest-library','.local/cnn-training-20261113/build/libvmweave_guest.so'],check=True)
c=json.loads(subprocess.check_output(['kubectl','-n','vmweave-test-b','get','sharedmemorychannel','dp-dev-20261105','-o','json']))
(R/'candidate-final-worker.log').write_bytes(subprocess.check_output(['kubectl','-n','vmweave-test-b','logs',c['status']['resourcePrefix']+'-worker','--all-containers=true']))
guest=json.loads(lab.ssh('sudo cat /run/vmweave-device-plugin/status.json').stdout);assert guest['ready'] and not guest['activeClient'];(R/'candidate-idle-guest-status.json').write_text(json.dumps(guest,indent=2)+'\n')
with (L/'switch-restore.log').open('w') as out:subprocess.run(['python3',str(L/'switch_runtime.py'),'restore'],stdout=out,stderr=subprocess.STDOUT,check=True)
for attempt in range(100):
 try:
  if lab.ssh('kubectl get --raw=/readyz',check=False).stdout.strip()=='ok':break
 except Exception:pass
 time.sleep(2)
else:raise TimeoutError('restored API')
public=json.loads(pathlib.Path('deploy/releases/v0.5.9.json').read_text())
subprocess.run(base+['run','--name','restored-published-basic','--case','basic','--guest-image','ghcr.io/woogiboogi1129/vmweave-device-plugin-guest@sha256:9cbbfb6c1501c84103f5e0f2fc921f384b11eea168a0f6971d7beb67b5384411','--library-sha256',public['guestLibrarySHA256']],check=True)
(R/'restored-plugin-values.json').write_text(lab.ssh('helm get values vmweave-device-plugin -n vmweave-device-plugin -o json').stdout)
subprocess.run(['python3',str(L/'finish.py')],check=True)
