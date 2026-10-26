import sys,json,subprocess,shlex,hashlib,time,os
from pathlib import Path
import rodinia_campaign as h
mode,label=sys.argv[1:3];copy_only=label=='copy';s=None
h.PUB=h.B/'package';CASES={'nw':['2048','10'],'lu':['-s','2064'],'srad':['2048','2048','0','127','0','127','0.5','2'],'sc':['10','20','256','65536','65536','1000','none','output.txt','1']}
refs=json.loads((h.B/'references.json').read_text());registry=[]
def run(f):subprocess.run([sys.executable,str(h.B/f)],check=True)
def stage(s):
 h.remote(s,'mkdir -p /tmp/short /tmp/short/trace-libs')
 files=[h.B/w for w in CASES]+[h.B/'copy_probe.py',h.R/'.local/thesis-isolation-20261012/bundle-stage/opt/flyt-cuda-libs/libcudart.so.12']
 subprocess.run(s['scp']+[str(f) for f in files]+['ubuntu@'+s['ip']+':/tmp/short/'],check=True)
 for w in CASES:assert h.remote(s,'sha256sum /tmp/short/'+w).split()[0]==hashlib.sha256((h.B/w).read_bytes()).hexdigest()
h.stage=stage
baseenv='env -u LD_PRELOAD LD_LIBRARY_PATH=/tmp/flyt-test:/tmp/short' if mode=='flyt' else 'env VMWEAVE_BROKER_SOCKET=/run/vmweave/gpu.sock VMWEAVE_MIRROR_DEVICE_VA=1 VMWEAVE_TRACE_REQUESTS=0 LD_LIBRARY_PATH=/opt/vmweave/lib:/tmp/short VMWEAVE_BULK_COPY='+('1' if mode=='on' else '0')
if mode!='flyt':baseenv+=' LD_PRELOAD=/opt/vmweave/lib/libvmweave_guest.so'
def capture_owned():
 ns=s['namespace'];pods=json.loads(h.k('get','pods','-n',ns,'-o','json'))['items']
 for p in pods:
  name=p['metadata']['name']
  if mode=='flyt' or name.startswith(s['name']+'-') or name.startswith('virt-launcher-'+s['name']+'-'):
   registry.append({'namespace':ns,'name':name,'uid':p['metadata']['uid']})
   h.k('label','pod',name,'-n',ns,'experiment=bulk-short-20261026','--overwrite')
 h.save(h.O/'sessions'/f'{label}-{mode}-pods.json',registry)
def command(cmd,output,timeout=600):
 p=subprocess.run(s['ssh']+[cmd],capture_output=True,text=True,timeout=timeout);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(p.stdout+p.stderr);assert p.returncode==0,(cmd,p.stderr[-600:]);return p
try:
 if mode=='flyt':
  h.drop_admin();os.environ['RODINIA_LABEL']='short-'+label
  run('prepare.py');run('server-pod.py');run('start-stack.py');s=json.loads((h.B/'state.json').read_text());s.update(json.loads((h.B/'ssh.json').read_text()));s['mode']='flyt'
  pods=json.loads(h.k('get','pods','-n',s['namespace'],'-o','json'))['items'];launcher=next(p for p in pods if p['metadata']['name'].startswith('virt-launcher-'));server=next(p for p in pods if p['metadata']['name']=='flyt-server');h.finish_affinity('flyt-short-'+label,launcher,server);stage(s)
 else:s=h.prepare_vmw(label+'-'+mode+('-retry' if label=='copy' and mode=='off' else ''))
 capture_owned();h.save(h.O/'sessions'/f'{label}-{mode}.json',{'name':s['name'],'namespace':s['namespace'],'started_unix':time.time()})
 if copy_only:
  file=mode+'-copy.json'
  if not (h.O/'copy'/file).exists():command('sudo '+baseenv+' python3 /tmp/short/copy_probe.py --out /tmp/short/'+file,h.O/'copy'/f'{mode}.log')
  if not (h.O/'copy'/file).exists():(h.O/'copy'/file).write_text(h.remote(s,'cat /tmp/short/'+file))
  # Separate instrumented process. strace counts returned bytes, never timed samples.
  root=h.B/'trace-bundle/root';libs=[root/'usr/bin/strace']+[p for p in root.rglob('*.so.*') if p.is_file()]
  subprocess.run(s['scp']+[str(p) for p in libs]+['ubuntu@'+s['ip']+':/tmp/short/trace-libs/'],check=True)
  command('sudo env LD_LIBRARY_PATH=/tmp/short/trace-libs /tmp/short/trace-libs/strace -qq -f -yy -s 1 -T -e trace=sendto,recvfrom,sendmsg,recvmsg,mmap,close -o /tmp/short/trace.log '+baseenv+' python3 /tmp/short/copy_probe.py --diagnostic --out /tmp/short/diag.json',h.O/'diagnostic'/f'{mode}.log')
  for remote,local in [('trace.log',mode+'-syscalls.log'),('diag.json',mode+'-result.json')]: (h.O/'diagnostic'/local).write_text(h.remote(s,'sudo cat /tmp/short/'+remote))
 else:
  roundn=int(label[1:]);repeats=1 if roundn==3 else 2
  for w,args in CASES.items():
   if w=='sc' and roundn!=1:continue
   count=1 if w=='sc' else repeats;d=h.O/'formal'/label/mode/w;d.mkdir(parents=True,exist_ok=False);target='/tmp/short/'+label+'-'+w
   print('START',label,mode,w,flush=True);started=time.time()
   (d/'gpu-before.csv').write_text(subprocess.check_output(['nvidia-smi','-i',h.GPU,'--query-gpu=uuid,pstate,clocks.sm,power.draw,temperature.gpu,memory.used','--format=csv'],text=True))
   p=command('mkdir -p '+target+' && cd '+target+' && sudo timeout -k 5 400 '+baseenv+' EXPERIMENT_REPEATS='+str(count)+' /tmp/short/'+w+' '+shlex.join(args),d/'run.log',450)
   rows=[json.loads(x.split('EXPERIMENT_SAMPLE ',1)[1]) for x in p.stdout.splitlines() if x.startswith('EXPERIMENT_SAMPLE ')];hashes=h.remote(s,'sha256sum '+target+'/output-*.bin');correct=len(rows)==count+1 and sum(x['warmup'] for x in rows)==1 and len(hashes.splitlines())==count+1 and all(x.split()[0]==refs[w] for x in hashes.splitlines());h.save(d/'result.json',{'mode':mode,'workload':w,'samples':rows,'hashes':hashes,'correct':correct,'started_unix':started,'finished_unix':time.time(),'binary_sha256':hashlib.sha256((h.B/w).read_bytes()).hexdigest()});assert correct
   print('DONE',label,mode,w,flush=True)
finally:
 if mode=='flyt':
  if h.get('namespace','bulk-flyt-1026'):run('cleanup.py')
 elif s:h.cleanup_vmw(s)
 h.drop_admin()
 for p in registry:
  current=h.get('pod',p['name'],p['namespace'])
  if current:
   assert current['metadata']['uid']==p['uid'] and current['status']['phase'] in ['Succeeded','Failed']
   h.k('delete','pod',p['name'],'-n',p['namespace'],'--wait=true','--timeout=90s')
 h.save(h.O/'sessions'/f'{label}-{mode}-cleanup.json',{'owned_pods_removed':True,'finished_unix':time.time()})
