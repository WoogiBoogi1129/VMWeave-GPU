"""Native guest lifecycle; shared immutable fixture and persistent prepared OS disk."""
import json,subprocess,time,uuid
from campaign import c,BASE,ROOT,OUT,CONDITIONS,measure
from binding import RESOURCE,to_native,to_vmweave,patch
class Native:
 native=True
 def __init__(self,name,cores=8):self.name=name;self.ns='ai-perf-baseline';self.out=OUT/'identities'/name;self.cores=cores
 def prepare(self):
  v=json.loads((BASE/'VirtualMachine-ai-perf-native.json').read_text());v['metadata']['name']=self.name
  spec=v['spec']['template']['spec'];spec['domain']['cpu']['cores']=self.cores;spec['domain']['devices']['gpus']=[{'deviceName':RESOURCE,'name':'gpu'}];spec['domain']['firmware']['uuid']=str(uuid.uuid4())
  c.create(v)
  obj=c.wait(lambda:(v if (v:=c.get('vmi',self.name,ns=self.ns)) and v.get('status',{}).get('phase')=='Running' and v['status'].get('interfaces') else None))
  self.ip=obj['status']['interfaces'][0]['ipAddress'];self.out=OUT/'identities'/self.name;self.out.mkdir(parents=True,exist_ok=False)
  opts=['-i',str(ROOT/'.local/thesis-isolation-20261012/artifacts/guest-key'),'-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(self.out/'known-hosts')]
  self.ssh=['ssh',*opts,'-o','ConnectTimeout=5','ubuntu@'+self.ip];self.scp=['scp',*opts]
  c.wait(lambda:subprocess.run(self.ssh+['true'],capture_output=True).returncode==0)
  c.call(self.ssh+['sudo modprobe nvidia; sudo modprobe nvidia_uvm; sudo timedatectl set-ntp false; mkdir -p /tmp/perf'])
  nodes="import os,stat;from pathlib import Path;dev={n:int(m) for line in Path('/proc/devices').read_text().splitlines() if len(parts:=line.split())==2 and (m:=parts[0]).isdigit() for n in [parts[1]]};items=[('/dev/nvidia0',195,0),('/dev/nvidiactl',195,255),('/dev/nvidia-uvm',dev['nvidia-uvm'],0)];[(os.mknod(p,stat.S_IFCHR|0o666,os.makedev(ma,mi)) if not Path(p).exists() else None) for p,ma,mi in items]"
  c.call(self.ssh+['sudo python3 -c '+__import__('shlex').quote(nodes)])
  c.call(self.scp+[str(ROOT/'experiments/ai-passthrough/runner/bench.py'),str(BASE/'small.pt'),str(BASE/'medium.pt'),str(BASE/'large.pt'),'ubuntu@'+self.ip+':/tmp/perf/'])
  pods=json.loads(c.k('get','pods','-n',self.ns,'-o','json'))['items'];pod=next(x for x in pods if x['metadata']['name'].startswith('virt-launcher-'+self.name+'-'))
  affinity=c.k('exec','-i','-n',c.NS,c.HELPER,'--','chroot','/host','python3','-',pod['metadata']['uid'],('32-39' if self.cores==8 else '32-43'),input=(ROOT/'experiments/evidence/campaign_affinity.py').read_text())
  (self.out/'affinity.json').write_text(affinity);c.save(self.out/'vmi.json',obj);c.save(self.out/'launcher.json',pod)
  clocks=[]
  for _ in range(5):
   t0=time.time();g=float(c.call(self.ssh+['date +%s.%N']));t1=time.time();clocks.append({'before':t0,'guest':g,'after':t1,'offset':g-(t0+t1)/2,'uncertainty':(t1-t0)/2})
  self.offset=min(clocks,key=lambda x:x['uncertainty'])['offset'];c.save(self.out/'clock-map.json',clocks)
  (self.out/'environment.txt').write_text(c.call(self.ssh+['uname -a; cat /proc/driver/nvidia/version; sha256sum /opt/flyt-evidence/driver/libcuda.so.1; sudo env LD_LIBRARY_PATH=/opt/flyt-evidence/driver /opt/flyt-evidence/driver/nvidia-smi --query-gpu=uuid,pci.bus_id,driver_version,power.limit --format=csv']))
  (self.out/'gpu.txt').write_text(c.call(self.ssh+['sudo env LD_LIBRARY_PATH=/opt/flyt-evidence/driver /opt/flyt-evidence/driver/nvidia-smi']))
 def benchcmd(self,args):
  import shlex
  return self.ssh+['sudo env LD_LIBRARY_PATH=/opt/flyt-evidence/driver:/opt/flyt-cuda-libs /opt/torch-venv/bin/python /tmp/perf/bench.py '+shlex.join(list(map(str,args)))]
 def cleanup(self):
  c.k('delete','vm',self.name,'-n',self.ns,'--wait=true','--timeout=90s');c.wait(lambda:not c.get('vmi',self.name,ns=self.ns));c.wait(lambda:not any(p['metadata']['name'].startswith('virt-launcher-'+self.name+'-') for p in json.loads(c.k('get','pods','-n',self.ns,'-o','json'))['items']));c.save(self.out/'cleanup.json',{'deleted':True,'utc':time.time()})
def pilot():
 patch('vm','ai-perf-native','ai-perf-baseline',{'spec':{'runStrategy':'Halted'}});c.wait(lambda:not c.get('vmi','ai-perf-native',ns='ai-perf-baseline'))
 to_native();v=Native('ai-perf-p-pilot-1016')
 try:
  v.prepare()
  for condition in CONDITIONS:measure(v,condition,'correctness',OUT/'pilot-passthrough'/('-'.join(map(str,condition))))
 finally:
  try:v.cleanup()
  finally:to_vmweave()
if __name__=='__main__':pilot()
