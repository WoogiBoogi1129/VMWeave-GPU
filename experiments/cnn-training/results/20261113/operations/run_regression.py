import subprocess,pathlib,json
L=pathlib.Path('.local/cnn-training-20261113');R=pathlib.Path('experiments/cnn-training/results/20261113')
assert json.loads((R/'candidate-accumulate/exit.json').read_text())['returncode']==0
image='localhost/vmweave-worker@'+(L/'worker-digest').read_text().strip()
subprocess.run(['python3','experiments/cnn-forward/runner/run.py','run','--connection',str(L/'forward-connection.json'),'--results',str(R/'regression'),'--name','candidate-forward','--backend','legacy','--case','matrix','--guest-library',str(L/'build/libvmweave_guest.so'),'--worker-image',image],check=True)
base=['python3','experiments/rnn-default/runner/run.py','--connection',str(L/'rnn-connection.json'),'--results',str(R/'regression')]
subprocess.run(base+['prepare'],check=True)
for name,case in [('candidate-mlp','mlp'),('candidate-lstm','lstm'),('candidate-lstm-repeat','lstm'),('candidate-basic-after','basic')]:
 subprocess.run(base+['run','--name',name,'--case',case,'--guest-library',str(L/'build/libvmweave_guest.so')],check=True)
c=json.loads(subprocess.check_output(['kubectl','-n','vmweave-test-b','get','sharedmemorychannel','dp-dev-20261105','-o','json']))
(R/'candidate-final-worker.log').write_bytes(subprocess.check_output(['kubectl','-n','vmweave-test-b','logs',c['status']['resourcePrefix']+'-worker','--all-containers=true']))
