import subprocess,time,json,pathlib
R=pathlib.Path.cwd();D=R/'.local/rodinia-threeway-20261025'; key=R/'.local/thesis-isolation-20261012/artifacts/guest-key'
ip=json.loads(subprocess.check_output(['kubectl','get','vmi','rodinia-native-1025','-n','ai-perf-baseline','-o','json']))['status']['interfaces'][0]['ipAddress']
ssh=['ssh','-i',str(key),'-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(D/'known-hosts'),'ubuntu@'+ip];scp=['scp','-i',str(key),'-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(D/'known-hosts')]
def run(s):subprocess.run(ssh+[s],check=True)
for _ in range(90):
 if subprocess.run(ssh+['true'],capture_output=True).returncode==0:break
 time.sleep(2)
else:raise RuntimeError('ssh timeout')
run('sudo mkdir -p /opt/flyt-evidence/driver; sudo chown -R ubuntu:ubuntu /opt/flyt-evidence')
for f in ['driver-source.tgz','firmware.tgz']:
 subprocess.run(scp+[str(R/'.local/pytorch-path-20260922'/f),'ubuntu@'+ip+':/opt/flyt-evidence/'],check=True)
subprocess.run(scp+[str(p) for p in (R/'.local/pytorch-path-20260922/driver').iterdir() if p.is_file()]+['ubuntu@'+ip+':/opt/flyt-evidence/driver/'],check=True)
with (R/'.local/thesis-isolation-20261012/guest-python-cuda.tgz').open('rb') as f:subprocess.run(ssh+['sudo tar -xz -C / opt/torch-venv opt/flyt-cuda-libs'],stdin=f,check=True)
run('sudo apt-get update -o Acquire::GzipIndexes=true && sudo apt-get install -y --no-install-recommends gcc make libelf-dev linux-headers-$(uname -r)')
run('cd /opt/flyt-evidence && tar -xzf driver-source.tgz && cd nvidia-580.173.02 && make -j8 modules')
run('sudo mkdir -p /lib/modules/$(uname -r)/updates/flyt; sudo cp /opt/flyt-evidence/nvidia-580.173.02/*.ko /lib/modules/$(uname -r)/updates/flyt/; sudo depmod -a; sudo mkdir -p /lib/firmware; sudo tar -xzf /opt/flyt-evidence/firmware.tgz -C /lib/firmware')
print('BOOTSTRAP COMPLETE',flush=True)
