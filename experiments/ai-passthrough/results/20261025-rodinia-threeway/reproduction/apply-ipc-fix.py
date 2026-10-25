import subprocess,json
from pathlib import Path
R=Path.cwd();B=R/'.local/rodinia-threeway-20261025';s=json.loads((B/'state.json').read_text());d=json.loads((B/'ssh.json').read_text());g=R/'.local/rodinia-threeway-20261023/flyt-guest/control-managers/target/release'
def ex(cmd):return subprocess.check_output(['kubectl','exec','-n',s['namespace'],'flyt-server','-c','server','--','sh','-c',cmd],text=True)
subprocess.run(['kubectl','cp','-c','server',str(g/'flyt-node-manager'),s['namespace']+'/flyt-server:/opt/flyt-test/flyt-node-manager-ipcfix'],check=True)
ex('pkill -f "^/opt/flyt-test/flyt-node-manager$"; ipcrm -q 0; ipcrm -q 1; chmod +x /opt/flyt-test/flyt-node-manager-ipcfix; nohup env -u LD_PRELOAD CUDA_VISIBLE_DEVICES=GPU-772181af-05a4-0c24-de59-8487bd37c142 CUDA_MPS_PIPE_DIRECTORY=/run/flyt-mps CUDA_MPS_LOG_DIRECTORY=/tmp/flyt-mps-log LD_LIBRARY_PATH=/opt/flyt-test:/usr/local/cuda/lib64:/usr/local/cuda/lib64/stubs RUST_LOG=debug /opt/flyt-test/flyt-node-manager-ipcfix > /tmp/node-ipcfix.log 2>&1 < /dev/null &')
subprocess.run(d['scp']+[str(g/'flyt-client-manager'),'ubuntu@'+s['ip']+':/tmp/flyt-test/flyt-client-manager-ipcfix'],check=True)
subprocess.run(d['ssh']+['sudo pkill -f "^/tmp/flyt-test/flyt-client-manager$"; sudo sh -c "nohup env RUST_LOG=debug /tmp/flyt-test/flyt-client-manager-ipcfix > /tmp/flyt-test/manager-ipcfix.log 2>&1 < /dev/null &"'],check=True)
