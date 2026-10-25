import json,subprocess,time
from pathlib import Path
B=Path('.local/rodinia-threeway-20261025');s=json.loads((B/'state.json').read_text());d=json.loads((B/'ssh.json').read_text())
def ex(cmd):return subprocess.check_output(['kubectl','exec','-n',s['namespace'],'flyt-server','-c','server','--','sh','-c',cmd],text=True)
env='env -u LD_PRELOAD CUDA_VISIBLE_DEVICES=GPU-772181af-05a4-0c24-de59-8487bd37c142 CUDA_MPS_PIPE_DIRECTORY=/run/flyt-mps CUDA_MPS_LOG_DIRECTORY=/tmp/flyt-mps-log LD_LIBRARY_PATH=/opt/flyt-test:/usr/local/cuda/lib64:/usr/local/cuda/lib64/stubs RUST_LOG=debug '
ex('env -u LD_PRELOAD -u LD_LIBRARY_PATH rpcbind')
for program,log in [('flyt-cluster-manager','cluster-final'),('flyt-node-manager-ipcfix','node-final')]:ex('nohup '+env+'/opt/flyt-test/'+program+' > /tmp/'+log+'.log 2>&1 < /dev/null &')
subprocess.run(d['ssh']+['sudo pkill -f "^/tmp/flyt-test/flyt-client-manager-ipcfix$"; sudo sh -c "nohup env RUST_LOG=debug /tmp/flyt-test/flyt-client-manager-ipcfix > /tmp/flyt-test/manager-final.log 2>&1 < /dev/null &"'],check=True)
print(ex('env -u LD_LIBRARY_PATH rpcinfo -p 127.0.0.1'))
