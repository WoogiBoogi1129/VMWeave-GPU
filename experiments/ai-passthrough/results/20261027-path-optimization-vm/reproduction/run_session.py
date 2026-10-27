import sys,json,subprocess,shlex,hashlib,time,os
from pathlib import Path
import rodinia_campaign as h
mode,label=sys.argv[1:3];copy_only=label.startswith('qual');s=None
h.PUB=h.B/('package-'+mode) if mode!='flyt' else h.PUB;
if mode!='flyt':h.images['worker']=json.loads((h.B/'images.json').read_text())['sanitizer' if label.startswith('qual-sanitizer') else mode]
if label.startswith('qual-spin'):
 key=label.removeprefix('qual-');h.images['worker']=json.loads((h.B/'images.json').read_text())[key];h.PUB=h.B/('package-'+key)
CASES={'nw':['2048','10'],'lu':['-s','2064'],'srad':['2048','2048','0','127','0','127','0.5','2'],'sc':['10','20','256','65536','65536','1000','none','output.txt','1']}
refs=json.loads((h.B/'references.json').read_text());registry=[]
def run(f):subprocess.run([sys.executable,str(h.B/f)],check=True)
def stage(s):
 h.remote(s,'mkdir -p /tmp/short /tmp/short/trace-libs')
 files=[h.B/w for w in CASES]+[h.B/'micro_probe.py',h.B/'correctness',h.B/'large_copy_gpu.py',h.R/'.local/thesis-isolation-20261012/bundle-stage/opt/flyt-cuda-libs/libcudart.so.12']
 subprocess.run(s['scp']+[str(f) for f in files]+['ubuntu@'+s['ip']+':/tmp/short/'],check=True)
 for w in CASES:assert h.remote(s,'sha256sum /tmp/short/'+w).split()[0]==hashlib.sha256((h.B/w).read_bytes()).hexdigest()
h.stage=stage
baseenv='env -u LD_PRELOAD LD_LIBRARY_PATH=/tmp/flyt-test:/tmp/short' if mode=='flyt' else 'env VMWEAVE_BROKER_SOCKET=/run/vmweave/gpu.sock VMWEAVE_MIRROR_DEVICE_VA=1 VMWEAVE_TRACE_REQUESTS=0 VMWEAVE_STATE_CACHE=0 VMWEAVE_MATH_CACHE=0 LD_LIBRARY_PATH=/opt/vmweave/lib:/tmp/short VMWEAVE_BULK_COPY=1'
if mode!='flyt':baseenv+=' LD_PRELOAD=/opt/vmweave/lib/libvmweave_guest.so'
if mode=='candidate':baseenv+=' VMWEAVE_NATIVE_MEMSET=1 VMWEAVE_BULK_DIRECT=1'
def capture_owned():
 ns=s['namespace'];pods=json.loads(h.k('get','pods','-n',ns,'-o','json'))['items']
 for p in pods:
  name=p['metadata']['name']
  if mode=='flyt' or name.startswith(s['name']+'-') or name.startswith('virt-launcher-'+s['name']+'-'):
   registry.append({'namespace':ns,'name':name,'uid':p['metadata']['uid']})
   h.k('label','pod',name,'-n',ns,'experiment=path-optimization-20261027','--overwrite')
 h.save(h.O/'sessions'/f'{label}-{mode}-pods.json',registry)
def command(cmd,output,timeout=600):
 p=subprocess.run(s['ssh']+[cmd],capture_output=True,text=True,timeout=timeout);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(p.stdout+p.stderr);assert p.returncode==0,(cmd,p.stderr[-600:]);return p
try:
 if mode=='flyt':
  h.drop_admin();os.environ['RODINIA_LABEL']='short-'+label
  run('prepare.py');run('server-pod.py');run('start-stack.py');s=json.loads((h.B/'state.json').read_text());s.update(json.loads((h.B/'ssh.json').read_text()));s['mode']='flyt'
  pods=json.loads(h.k('get','pods','-n',s['namespace'],'-o','json'))['items'];launcher=next(p for p in pods if p['metadata']['name'].startswith('virt-launcher-'));server=next(p for p in pods if p['metadata']['name']=='flyt-server');h.finish_affinity('flyt-short-'+label,launcher,server);stage(s)
 else:s=h.prepare_vmw(label+'-'+mode)
 capture_owned();h.save(h.B/'active-session.json',s);h.save(h.O/'sessions'/f'{label}-{mode}.json',{'name':s['name'],'namespace':s['namespace'],'started_unix':time.time()})
 if copy_only:
  d=h.O/'qualification'/label/mode;d.mkdir(parents=True,exist_ok=False)
  command('sudo timeout -k 5 180 '+baseenv+' /tmp/short/correctness',d/'correctness.log',200)
  library='/tmp/flyt-test/cricket-client.so' if mode=='flyt' else '/opt/vmweave/lib/libvmweave_guest.so'
  if mode!='flyt':
   command('sudo timeout -k 5 180 '+baseenv+' python3 /tmp/short/large_copy_gpu.py --library '+library+' --out /tmp/short/large-copy.json',d/'large-copy.log',200)
   (d/'large-copy.json').write_text(h.remote(s,'cat /tmp/short/large-copy.json'))
  if label.startswith('qual-spin'):
   import resource_diag
   cpu_before=resource_diag.snapshot(h,s)
  command('sudo timeout -k 5 180 '+baseenv+' python3 /tmp/short/micro_probe.py --library '+library+' --out /tmp/short/micro.json',d/'micro.log',200)
  if label.startswith('qual-spin'):
   cpu_after=resource_diag.snapshot(h,s)
   h.save(d/'resource-accounting.json',{'before':cpu_before,'after':cpu_after,'summary':resource_diag.summarize(cpu_before,cpu_after)})
  (d/'micro.json').write_text(h.remote(s,'cat /tmp/short/micro.json'))
  if label=='qual-recovery' and mode=='candidate':
   import lifecycle_vm; lifecycle_vm.qualify(h,s,baseenv,d/'lifecycle')
   import restart_vm; restart_vm.qualify(h,s,baseenv,d/'vm-recreation')
   capture_owned()
 else:
  roundn=int(label[1:]);repeats=3
  for w,args in CASES.items():
   count=1 if w=='sc' else repeats;d=h.O/'formal'/label/mode/w;d.mkdir(parents=True,exist_ok=False);target='/tmp/short/'+label+'-'+w
   print('START',label,mode,w,flush=True);started=time.time()
   (d/'gpu-before.csv').write_text(subprocess.check_output(['nvidia-smi','-i',h.GPU,'--query-gpu=uuid,pstate,clocks.sm,power.draw,temperature.gpu,memory.used','--format=csv'],text=True))
   p=command('mkdir -p '+target+' && cd '+target+' && sudo timeout -k 5 400 '+baseenv+' EXPERIMENT_REPEATS='+str(count)+' /tmp/short/'+w+' '+shlex.join(args),d/'run.log',450)
   rows=[json.loads(x.split('EXPERIMENT_SAMPLE ',1)[1]) for x in p.stdout.splitlines() if x.startswith('EXPERIMENT_SAMPLE ')];hashes=h.remote(s,'sha256sum '+target+'/output-*.bin');correct=len(rows)==count+1 and sum(x['warmup'] for x in rows)==1 and len(hashes.splitlines())==count+1 and all(x.split()[0]==refs[w] for x in hashes.splitlines());h.save(d/'result.json',{'mode':mode,'workload':w,'samples':rows,'hashes':hashes,'correct':correct,'started_unix':started,'finished_unix':time.time(),'binary_sha256':hashlib.sha256((h.B/w).read_bytes()).hexdigest()});assert correct
   print('DONE',label,mode,w,flush=True)
  d=h.O/'micro'/label/mode;d.mkdir(parents=True,exist_ok=False)
  library='/tmp/flyt-test/cricket-client.so' if mode=='flyt' else '/opt/vmweave/lib/libvmweave_guest.so'
  command('sudo timeout -k 5 180 '+baseenv+' python3 /tmp/short/micro_probe.py --library '+library+' --out /tmp/short/micro.json',d/'run.log',200)
  (d/'result.json').write_text(h.remote(s,'cat /tmp/short/micro.json'))
finally:
 if s and mode!='flyt':
  h.save(h.O/'sessions'/f'{label}-{mode}-final-channel.json',h.get('sharedmemorychannel',s['name']))
  (h.O/'sessions'/f'{label}-{mode}-worker.log').write_text(h.k('logs',s['worker'],'-n',s['namespace']))
  if label.startswith('qual-sanitizer'):
   report=h.k('exec',s['worker'],'-n',s['namespace'],'--','sh','-c','cat /tmp/memcheck-*.log')
   (h.O/'qualification'/label/mode/'memcheck.log').write_text(report)
 if mode=='flyt':
  if h.get('namespace','path-flyt-1027'):run('cleanup.py')
 elif s:h.cleanup_vmw(s)
 h.drop_admin()
 for p in registry:
  current=h.get('pod',p['name'],p['namespace'])
  if current:
   assert current['metadata']['uid']==p['uid'] and current['status']['phase'] in ['Succeeded','Failed']
   h.k('delete','pod',p['name'],'-n',p['namespace'],'--wait=true','--timeout=90s')
 h.save(h.O/'sessions'/f'{label}-{mode}-cleanup.json',{'owned_pods_removed':True,'finished_unix':time.time()})
