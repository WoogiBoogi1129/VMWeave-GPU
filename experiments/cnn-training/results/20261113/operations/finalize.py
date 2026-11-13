import pathlib,subprocess,time,json,sys
sys.path.insert(0,'.local/device-plugin-20261105');import lab
R=pathlib.Path('experiments/cnn-training/results/20261113');L=pathlib.Path('.local/cnn-training-20261113')
end=time.monotonic()+900
while not (R/'candidate-final-worker.log').exists():
 if time.monotonic()>end:raise TimeoutError('regression incomplete')
 time.sleep(2)
assert json.loads((R/'regression/candidate-basic-after/exit.json').read_text())['returncode']==0
command='export PYTHONPATH=/repo/.local/thesis-isolation-20261012/bundle-stage/opt/torch-venv/lib/python3.10/site-packages; export LD_LIBRARY_PATH=/repo/.local/thesis-isolation-20261012/bundle-stage/opt/flyt-cuda-libs:/usr/local/cuda/lib64; python3 experiments/cnn-training/audit_tensors.py'
with (R/'tensor-audit.log').open('w') as out:
 subprocess.run(['podman','run','--rm','--entrypoint','/bin/bash','-v',str(pathlib.Path.cwd())+':/repo','-w','/repo','localhost/vmweave-rnn-builder:validated','-ec',command],stdout=out,stderr=subprocess.STDOUT,check=True)
guest=json.loads(lab.ssh('sudo cat /run/vmweave-device-plugin/status.json').stdout)
assert guest['ready'] and not guest['activeClient']
(R/'candidate-idle-guest-status.json').write_text(json.dumps(guest,indent=2)+'\n')
with (L/'switch-restore.log').open('w') as out:
 subprocess.run(['python3',str(L/'switch_runtime.py'),'restore'],stdout=out,stderr=subprocess.STDOUT,check=True)
for attempt in range(100):
 try:
  if lab.ssh('kubectl get --raw=/readyz',check=False).stdout.strip()=='ok':break
 except Exception:pass
 time.sleep(2)
else:raise TimeoutError('restored Guest API')
release=json.loads(pathlib.Path('deploy/releases/device-plugin-v0.1.1.json').read_text())
print(release.keys(),flush=True)
public=json.loads(pathlib.Path('deploy/releases/v0.5.9.json').read_text())
subprocess.run(['python3','experiments/rnn-default/runner/run.py','--connection',str(L/'rnn-connection.json'),'--results',str(R/'regression'),'run','--name','restored-published-basic','--case','basic','--guest-image','ghcr.io/woogiboogi1129/vmweave-device-plugin-guest@sha256:9cbbfb6c1501c84103f5e0f2fc921f384b11eea168a0f6971d7beb67b5384411','--library-sha256',public['guestLibrarySHA256']],check=True)
values=lab.ssh('helm get values vmweave-device-plugin -n vmweave-device-plugin -o json').stdout
(R/'restored-plugin-values.json').write_text(values)
subprocess.run(['python3',str(L/'finish.py')],check=True)
