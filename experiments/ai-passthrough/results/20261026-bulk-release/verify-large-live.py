from pathlib import Path
import json,subprocess,hashlib
R=Path.cwd();D=R/'.local/v054-release-20261026';NS='vmweave-test-a';NAME='vmweave-k8s-01';KEY=str(R/'.local/system-comparison-20261001/artifacts/guest-key')
v=json.loads(subprocess.check_output(['kubectl','get','vmi',NAME,'-n',NS,'-o','json'],text=True));ip=v['status']['interfaces'][0]['ipAddress'];ssh=['ssh','-i',KEY,'-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','-o','ConnectTimeout=5','ubuntu@'+ip];scp=['scp','-i',KEY,'-o','BatchMode=yes']
def remote(cmd,name,timeout=180):
 p=subprocess.run(ssh+[cmd],capture_output=True,text=True,timeout=timeout);(D/(name+'.log')).write_text(p.stdout+p.stderr);assert p.returncode==0,(name,p.stderr);return p.stdout
remote('mkdir -p /tmp/vmweave-v054-check','live-test-dir')
subprocess.run(scp+[str(R/'tests/integration/large_copy_gpu.py'),str(R/'.local/large-copy-20261023/needle'),str(R/'.local/large-copy-20261023/lud'),str(R/'.local/thesis-isolation-20261012/bundle-stage/opt/flyt-cuda-libs/libcudart.so.12'),'ubuntu@'+ip+':/tmp/vmweave-v054-check/'],check=True)
remote('sudo env VMWEAVE_BULK_COPY=1 VMWEAVE_BROKER_SOCKET=/run/vmweave/gpu.sock python3 /tmp/vmweave-v054-check/large_copy_gpu.py --library /opt/vmweave/lib/libvmweave_guest.so --out /tmp/vmweave-v054-check/large.json','live-large-copy',300)
(D/'live-large-copy.json').write_text(remote('cat /tmp/vmweave-v054-check/large.json','live-large-fetch'))
expected=json.loads((R/'experiments/ai-passthrough/results/20261023-large-copy/rodinia-comparison.json').read_text());rows=[]
for name,binary,args in [('nw','needle','2048 10'),('lud256','lud','-s 256 -v'),('lud2064','lud','-s 2064')]:
 directory='/tmp/vmweave-v054-check/'+name
 remote('mkdir -p '+directory+' && cd '+directory+' && sudo env VMWEAVE_BULK_COPY=1 VMWEAVE_BROKER_SOCKET=/run/vmweave/gpu.sock VMWEAVE_MIRROR_DEVICE_VA=1 LD_PRELOAD=/opt/vmweave/lib/libvmweave_guest.so LD_LIBRARY_PATH=/opt/vmweave/lib:/tmp/vmweave-v054-check /tmp/vmweave-v054-check/'+binary+' '+args,'live-'+name)
 digest=remote('sha256sum '+directory+'/full-output.bin','live-'+name+'-sha').split()[0];assert digest==next(r['native_host_sha256'] for r in expected if r['workload']==name);rows.append({'workload':name,'sha256':digest,'match':True})
(D/'live-rodinia.json').write_text(json.dumps(rows,indent=2))
remote('sudo rm -rf /tmp/vmweave-v054-check','live-test-cleanup')
print('Live large copies and NW/LU correctness PASS')
