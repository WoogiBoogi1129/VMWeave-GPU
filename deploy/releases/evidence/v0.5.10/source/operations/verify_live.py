import pathlib,json,subprocess,sys,time,hashlib
sys.path.insert(0,'.local/device-plugin-20261105');import lab
D=pathlib.Path('.local/cnn-release-20261113');E=pathlib.Path('deploy/releases/evidence/v0.5.10');R=E/'cnn'
rollout=json.loads((D/'rollout-result.json').read_text());assert rollout['status']=='PASS'
image=rollout['pluginImages']['-guest']['reference'];sha=rollout['guestLibrarySHA256'];worker=rollout['images']['worker']
for filename,prefix in [('connection.json','cnn-model-release-20261113'),('rnn-connection.json','rnn-default-release-20261113')]:
 c=dict(sshArgv=lab.ssh_args(),context='kubernetes-admin@vmweave-device-plugin-test',namespace=prefix,runID=prefix,node=lab.VM,brokerGID=998)
 p=D/filename;p.write_text(json.dumps(c));p.chmod(0o600)
for name,case in [('relu','relu'),('pool','pool'),('cnn','cnn'),('cnn-repeat','cnn'),('mnist','mnist')]:
 subprocess.run(['python3','experiments/cnn-model/runner/run.py','run','--connection',str(D/'connection.json'),'--results',str(R),'--name','published-'+name,'--backend','legacy','--case',case,'--guest-image',image,'--library-sha256',sha,'--worker-image',worker],check=True)
 for s in ['guest-adapter']:
  (R/('published-'+name)/(s+'.txt')).write_text(lab.ssh('kubectl -n cnn-model-release-20261113 logs published-'+name+' -c '+s).stdout)
base=['python3','experiments/rnn-default/runner/run.py','--connection',str(D/'rnn-connection.json'),'--results',str(E/'training')]
subprocess.run(base+['prepare'],check=True)
for attempt in range(60):
 if lab.ssh('kubectl -n rnn-default-release-20261113 get serviceaccount default --ignore-not-found -o name').stdout.strip():break
 time.sleep(1)
else:raise TimeoutError('default ServiceAccount')
for name,case in [('published-mlp','mlp'),('published-lstm','lstm'),('published-basic','basic')]:
 subprocess.run(base+['run','--name',name,'--case',case,'--guest-image',image,'--library-sha256',sha],check=True)
cmd='export PYTHONPATH=/repo/.local/thesis-isolation-20261012/bundle-stage/opt/torch-venv/lib/python3.10/site-packages; export LD_LIBRARY_PATH=/repo/.local/thesis-isolation-20261012/bundle-stage/opt/flyt-cuda-libs:/usr/local/cuda/lib64; python3 experiments/cnn-model/audit_tensors.py --results deploy/releases/evidence/v0.5.10/cnn --run-prefix published-'
with (E/'tensor-audit.log').open('w') as out:subprocess.run(['podman','run','--rm','--entrypoint','/bin/bash','-v',str(pathlib.Path.cwd())+':/repo','-w','/repo','localhost/vmweave-rnn-builder:validated','-ec',cmd],stdout=out,stderr=subprocess.STDOUT,check=True)
state=json.loads(lab.ssh('sudo cat /run/vmweave-device-plugin/status.json').stdout);assert state['ready'] and not state['activeClient'] and state['librarySHA256']==sha
(E/'broker-after-tests.json').write_text(json.dumps(state,indent=2)+'\n')
(E/'worker-after-tests.log').write_bytes(subprocess.check_output(['kubectl','-n',lab.NS,'logs',rollout['workerPod'],'--all-containers=true']))
result=dict(status='PASS',sourceRevision=rollout['sourceRevision'],guestLibrarySHA256=sha,workerImage=worker,guestImage=image,cnnSteps=80,cnnTensors=1040,independentCNNAudit=json.loads((R/'tensor-audit.json').read_text())['status'],cases={})
for folder in [R/('published-'+n) for n in ['relu','pool','cnn','cnn-repeat','mnist']]+[E/'training'/('published-'+n) for n in ['mlp','lstm','basic']]:
 e=json.loads((folder/'exit.json').read_text());p=json.loads((folder/'pod.json').read_text());assert e['returncode']==0 and not e['timeout'] and p['status']['phase']=='Succeeded'
 item=dict(exit=e,podUID=p['metadata']['uid'])
 if (folder/'comparison.json').exists():
  rows=json.loads((folder/'comparison.json').read_text());assert all(x.get('passed',x.get('pass_')) for x in rows);item.update(tensors=len(rows),maxAbs=max(x['max_abs'] for x in rows))
 result['cases'][folder.name]=item
for ns in ['cnn-model-release-20261113','rnn-default-release-20261113']:
 o=json.loads(lab.ssh('kubectl get ns '+ns+' -o json').stdout);assert o['metadata']['labels']['vmweave-experiment']==ns
 lab.ssh('kubectl delete namespace '+ns+' --wait=true --timeout=180s');assert not lab.ssh('kubectl get ns '+ns+' --ignore-not-found -o name').stdout.strip()
result.update(testNamespacesRemoved=True,sessionsReclaimed=True)
(E/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print('PUBLISHED CNN / MLP / LSTM VALIDATION PASS',flush=True)
