"""Campaign orchestration using UID-scoped VMWeave lifecycle primitives."""
import json,os,sys,time,subprocess,shutil,shlex,itertools,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'.local/ai-passthrough-20261016';OUT=ROOT/'experiments/ai-passthrough/results/20261016'
os.environ['SM_TEST_OUT']=str(BASE/'audit');os.environ['SM_TEST_GPU']='GPU-c654d43e-43f8-c28e-77c2-1f17a0cbf46a'
sys.path.insert(0,str(ROOT/'experiments/sm-core-limit/runner'))
import vmweave
c=vmweave.common;s=vmweave.session;c.OUT=s.OUT=BASE/'audit';c.HELPER=s.HELPER='ai-perf-admin-1016'
def ready_k(*args,**kw):
 args=tuple('40-43' if x=='48-51' else x for x in args)
 if "input" in kw and "No QEMU/Worker process matched" in kw["input"]:kw["input"]=kw["input"].replace("'flyt-shm-worker'", "'flyt-shm-worker','flyt-shm-session-worker'")
 end=time.monotonic()+120
 while True:
  try:return c.k(*args,**kw)
  except RuntimeError as e:
   if 'No QEMU/Worker process matched exact Pod UID' not in str(e) or time.monotonic()>end:raise
   time.sleep(2)
s.k=ready_k
def persistent_call(args,**kw):
 args=list(map(str,args))
 if any(x.endswith('/create-channel.py') for x in args):
  args=[('VM' if x=='Allocation' else x) for x in args]
  result=c.call(args,**kw);ns=args[args.index('--namespace')+1];name=args[args.index('--vm')+1]
  c.wait(lambda:c.get(s.CHAN,name,ns=ns).get('status',{}).get('phase')=='Stopped')
  c.k('patch','vm',name,'-n',ns,'--type=merge','-p','{"spec":{"runStrategy":"Always"}}')
  return result
 return c.call(args,**kw)
s.call=persistent_call
CONDITIONS=list(itertools.product(['small','medium','large'],[32,1024],['resident','transfer']))
class VM(vmweave.Canary):
 def __init__(self,name):
  super().__init__(name,'idle-reset',100);self.memory=8192;self.profile_name='ai-perf-vm-core100-1016'
 def prepare(self):
  self.thread=threading.Thread(target=self.install,daemon=True);self.thread.start()
  try:s.Session.prepare(self)
  finally:self.stop_gate.set();self.thread.join(timeout=10)
  if self.gate_error:raise RuntimeError(self.gate_error)
  c.call(self.scp+[str(BASE/'build/libflyt_guest.so'),'ubuntu@'+self.ip+':/tmp/perf/'])
  c.call(self.ssh+['ln -sf libflyt_guest.so /tmp/perf/libcuda.so.1'])
  c.call(self.scp+[str(ROOT/'runtime/shm/control/guest_broker.py'),'ubuntu@'+self.ip+':/tmp/perf/'])
  command=self.command('guest_broker.py',['--library','/tmp/perf/libflyt_guest.so'])[-1].replace('/tmp/perf/guest_broker.py ','python3 /tmp/perf/guest_broker.py ')
  c.call(self.ssh+['nohup '+command+' > /tmp/perf/broker.log 2>&1 < /dev/null &'])
  c.wait(lambda:subprocess.run(self.ssh+['sudo test -S /run/vmweave/gpu.sock'],capture_output=True).returncode==0)
  with (ROOT/'.local/thesis-isolation-20261012/guest-python-cuda.tgz').open('rb') as f:subprocess.run(self.ssh+['sudo tar -xz -C / opt/torch-venv opt/flyt-cuda-libs'],stdin=f,check=True)
  c.call(self.scp+[str(Path(__file__).with_name('bench.py')),'ubuntu@'+self.ip+':/tmp/perf/'])
  for model in ['small','medium','large']:
   file=BASE/(model+'.pt')
   if not file.exists():
    c.call(self.ssh+[f'LD_LIBRARY_PATH=/opt/flyt-cuda-libs /opt/torch-venv/bin/python /tmp/perf/bench.py --mode fixture --model {model} --fixture /tmp/perf/{model}.pt --out /tmp/unused'],timeout=120)
    c.call(self.scp+['ubuntu@'+self.ip+':/tmp/perf/'+model+'.pt',str(file)])
   else:c.call(self.scp+[str(file),'ubuntu@'+self.ip+':/tmp/perf/'])
  c.save(self.out/'vmi.json',self.get('vmi',self.name));c.save(self.out/'worker.json',self.get('pod',self.worker))
 def benchcmd(self,args):
  cmd=self.command('bench.py',args)
  cmd[-1]=cmd[-1].replace('LD_LIBRARY_PATH=/tmp/perf','FLYT_BROKER_SOCKET=/run/vmweave/gpu.sock LD_PRELOAD=/tmp/perf/libflyt_guest.so LD_LIBRARY_PATH=/tmp/perf:/opt/flyt-cuda-libs').replace('/tmp/perf/bench.py ','/opt/torch-venv/bin/python /tmp/perf/bench.py ')
  return cmd
 def cleanup(self):
  self.close()
  if self.uid:
   for kind in [s.CHAN,'vm','pvc']:c.k('delete',kind,self.name,'-n',self.ns,'--ignore-not-found','--wait=true','--timeout=60s')
   c.k('delete','pv',self.name,'--ignore-not-found','--wait=true','--timeout=60s')
   c.admin(['chroot','/host','rm','-rf','/var/lib/vmweave/thesis-isolation-20261012/'+self.name])
def measure(v,condition,mode,dest):
 model,batch,inp=condition;dest.mkdir(parents=True,exist_ok=False);prefix='/tmp/perf/'+dest.name
 args=['--model',model,'--batch',batch,'--input',inp,'--mode',mode,'--fixture','/tmp/perf/'+model+'.pt','--out',prefix]
 pods=json.loads(c.k('get','pods','-n',v.ns,'-o','json'))['items']
 uids=[x['metadata']['uid'] for x in pods if x['metadata']['name'].startswith('virt-launcher-'+v.name+'-') or x['metadata']['name']==getattr(v,'worker','')]
 cpulog=(dest/'host-cpu.jsonl').open('w')
 cpup=subprocess.Popen(['kubectl','exec','-i','-n',c.NS,c.HELPER,'--','chroot','/host','python3','-',*uids],stdin=subprocess.PIPE,stdout=cpulog,stderr=subprocess.DEVNULL,text=True)
 cpup.stdin.write(Path(__file__).with_name('host_cpu.py').read_text());cpup.stdin.close()
 with (dest/'stdout.txt').open('w') as out,(dest/'stderr.txt').open('w') as err,(dest/'gpu.csv').open('w') as gpu:
  p=subprocess.Popen(v.benchcmd(args),stdout=out,stderr=err);deadline=time.monotonic()+900
  gpu.write('utc,utilization,memory_MiB,clock_MHz,power_W,temperature_C\n')
  while p.poll() is None:
   if time.monotonic()>deadline:p.terminate();p.wait(timeout=10);break
   cmd=['nvidia-smi','-i',s.GPU,'--query-gpu=utilization.gpu,memory.used,clocks.sm,power.draw,temperature.gpu','--format=csv,noheader,nounits']
   if hasattr(v,'native'):cmd=v.ssh+['sudo env LD_LIBRARY_PATH=/opt/flyt-evidence/driver /opt/flyt-evidence/driver/nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,power.draw,temperature.gpu --format=csv,noheader,nounits']
   try:r=subprocess.run(cmd,capture_output=True,text=True,timeout=10);line=r.stdout.strip()
   except subprocess.TimeoutExpired:line=''
   gpu.write(str(time.time())+','+line+'\n');gpu.flush();time.sleep(1)
  cpup.terminate();cpup.wait(timeout=10);cpulog.close()
  c.save(dest/'exit.json',{'returncode':p.returncode})
  if p.returncode:raise RuntimeError('Benchmark failed: '+str(dest))
 c.call(v.scp+['ubuntu@'+v.ip+':'+prefix+'.json',str(dest/'result.json')])
 result=json.loads((dest/'result.json').read_text());result['guest_clock_offset_seconds']=getattr(v,'offset',0)
 if mode=='performance':
  for field in ['start_utc','end_utc']:result[field+'_guest']=result[field];result[field]-=getattr(v,'offset',0)
 c.save(dest/'result.json',result)
 if mode=='correctness':c.call(v.scp+['ubuntu@'+v.ip+':'+prefix+'.pt',str(dest/'tensors.pt')])
 print('COMPLETE',str(dest),flush=True)
def pilot():
 digest=c.admin(['chroot','/host','podman','image','inspect','localhost/vmweave-worker:ai-perf-persistent','--format','{{.Digest}}']).strip();s.IMAGES['worker']='localhost/vmweave-worker@'+digest
 v=VM('ai-perf-w-pilot-'+time.strftime('%H%M%S'))
 try:
  v.prepare()
  for condition in CONDITIONS:
   try:measure(v,condition,'correctness',OUT/'pilot-vmweave'/('-'.join(map(str,condition))))
   except RuntimeError as e:print('CONDITION FAILED',condition,str(e),flush=True)
 finally:v.cleanup()
if __name__=='__main__':pilot()
