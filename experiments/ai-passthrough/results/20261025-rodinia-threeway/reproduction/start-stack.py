import json,subprocess,time,secrets,shlex
from pathlib import Path
R=Path.cwd();B=R/'.local/rodinia-threeway-20261025';O=R/'experiments/ai-passthrough/results/20261025-rodinia-threeway';s=json.loads((B/'state.json').read_text());NS=s['namespace'];POD='flyt-server'
def k(*a,**kw):return subprocess.check_output(['kubectl',*map(str,a)],text=True,**kw)
def ex(cmd,**kw):return k('exec','-i','-n',NS,POD,'-c','server','--','sh','-c',cmd,**kw)
def wait(fn,seconds=240):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if (v:=fn()):return v
  time.sleep(2)
 raise TimeoutError('stack wait')
p=wait(lambda:x if (x:=json.loads(k('get','pod',POD,'-n',NS,'-o','json')))['status'].get('phase')=='Running' and all(c['ready'] for c in x['status'].get('containerStatuses',[])) else None)
ip=p['status']['podIP'];s['serverIP']=ip;(B/'state.json').write_text(json.dumps(s,indent=2));(O/'flyt-server-pod.json').write_text(json.dumps(p,indent=2))
# Runtime-only setup fixes; source/patch provenance is saved in results.
for source,target in [('/etc/services','/etc/services'),('/etc/protocols','/etc/protocols')]:
 k('cp',source,NS+'/'+POD+':'+target,'-c','server')
manager=R/'.local/rodinia-threeway-20261023/flyt-guest/control-managers/target/release/flyt-node-manager'
k('cp',str(manager),NS+'/'+POD+':/opt/flyt-test/flyt-node-manager','-c','server')
secret=secrets.token_hex(20)
js='db.getSiblingDB("admin").createUser('+json.dumps({'user':'flyt_test','pwd':secret,'roles':[{'role':'root','db':'admin'}]})+');\n'
js+='db.getSiblingDB("flyt_test").vm_required_resources.insertOne('+json.dumps({'vm_ip':s['ip'],'host_ip':ip,'compute_units':188,'memory':8192})+');\n'
k('exec','-i','-n',NS,POD,'-c','mongo','--','mongosh','--quiet','--port','28025',input=js)
cluster=f'''[vm-resource-db]\nhost="127.0.0.1"\nport=28025\nuser="flyt_test"\npassword="{secret}"\ndbname="flyt_test"\n[ports]\nnode=12401\nclient=12402\n[virt-server-auto-deallocate]\nenabled=false\ngrace-period=60\n[ipc]\nmqueue-path="/tmp/flyt-rmgr-queue"\nfrontend-socket="/tmp/flyt-frontend-socket"\n[migration]\nckp-path="/tmp/flyt-ckp-path"\n'''
node=f'''[resource-manager]\naddress="{ip}"\nport=12401\n[virt-server]\nprogram-path="/opt/flyt-test/cricket-rpc-server"\nthread-mode=0\n[ipc]\nmqueue-path="/tmp/flyt-servernode-queue"\n'''
paths={'/home/armaan/Work/SYNERG/Puru_Flyt/flyt_src/flyt/configs/cluster-mgr-config.toml':cluster,'/home/ub-11/Armaan_Puru_Flyt/flyt_src/flyt/configs/servnode-config.toml':node}
for path,data in paths.items():ex('mkdir -p '+shlex.quote(str(Path(path).parent))+'; cat > '+shlex.quote(path),input=data)
ex('ln -s /flyt-channel/'+s['aid']+'/channel /dev/shm/ivshmem-0-ub11.dat; mkdir -p /run/flyt-mps /tmp/flyt-mps-log; env -u LD_PRELOAD -u LD_LIBRARY_PATH rpcbind; true')
env='env -u LD_PRELOAD CUDA_VISIBLE_DEVICES=GPU-772181af-05a4-0c24-de59-8487bd37c142 CUDA_MPS_PIPE_DIRECTORY=/run/flyt-mps CUDA_MPS_LOG_DIRECTORY=/tmp/flyt-mps-log LD_LIBRARY_PATH=/opt/flyt-test:/usr/local/cuda/lib64:/usr/local/cuda/lib64/stubs RUST_LOG=debug '
ex('ln -s /usr/local/cuda/lib64/stubs/libnvidia-ml.so.1 /opt/flyt-test/libnvidia-ml.so; ln -s /usr/local/cuda/lib64/stubs/libcuda.so.1 /opt/flyt-test/libcuda.so')
ex(env+'nvidia-cuda-mps-control -d')
for name in ['cluster','node']:
 ex('nohup '+env+'/opt/flyt-test/flyt-'+name+'-manager > /tmp/'+name+'.log 2>&1 < /dev/null &')
key=R/'.local/thesis-isolation-20261012/artifacts/guest-key';opts=['-i',str(key),'-o','BatchMode=yes','-o','ConnectTimeout=5','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(B/'known-hosts')];ssh=['ssh',*opts,'ubuntu@'+s['ip']];scp=['scp',*opts]
wait(lambda:subprocess.run(ssh+['true'],capture_output=True).returncode==0)
subprocess.run(ssh+['mkdir -p /tmp/flyt-test'],check=True)
g=R/'.local/rodinia-threeway-20261023/flyt-guest'
files=[g/'cpu/cricket-client.so',g/'submodules/libtirpc/install/lib/libtirpc.so.3',g/'control-managers/target/release/flyt-client-manager',R/'.local/large-copy-20261023/needle',R/'.local/large-copy-20261023/lud']
subprocess.run(scp+list(map(str,files))+['ubuntu@'+s['ip']+':/tmp/flyt-test/'],check=True)
runtime=R/'.local/thesis-isolation-20261012/bundle-stage/opt/flyt-cuda-libs/libcudart.so.12'
subprocess.run(scp+[str(runtime),'ubuntu@'+s['ip']+':/tmp/flyt-test/native-cudart.so'],check=True)
subprocess.run(ssh+['sudo mkdir -p /usr/local/cuda/lib64; sudo cp /tmp/flyt-test/native-cudart.so /usr/local/cuda/lib64/libcudarto.so'],check=True)
client=f'''[resource-manager]\naddress="{ip}"\nport=12402\n[vcuda-client]\nprocess-monitor-period=60\n[ipc]\nmqueue-path="/tmp/flyt-client-mgr"\n'''
subprocess.run(ssh+['sudo mkdir -p /home/vm/flyt_src/flyt/configs; sudo tee /home/vm/flyt_src/flyt/configs/client-mgr.toml >/dev/null'],input=client,text=True,check=True)
subprocess.run(ssh+['ln -sf cricket-client.so /tmp/flyt-test/libcudart.so.12; sudo sh -c "nohup env RUST_LOG=debug /tmp/flyt-test/flyt-client-manager > /tmp/flyt-test/manager.log 2>&1 < /dev/null &"'],check=True)
(B/'ssh.json').write_text(json.dumps({'ssh':ssh,'scp':scp},indent=2));print('Flyt stack started',flush=True)
