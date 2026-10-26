import json,subprocess,shlex,time,hashlib,os
from pathlib import Path
import rodinia_campaign as h
CASES={'nw':['2048','10'],'lu':['-s','2064'],'srad':['2048','2048','0','127','0','127','0.5','2'],'sc':['10','20','256','65536','65536','1000','none','output.txt','1']}
def stage(s):
 expected=json.loads((h.O/'manifest.json').read_text())['binaries']
 for name in CASES:assert hashlib.sha256((h.B/name).read_bytes()).hexdigest()==expected[name]
 h.remote(s,'mkdir -p /tmp/steady')
 runtime=h.R/'.local/thesis-isolation-20261012/bundle-stage/opt/flyt-cuda-libs/libcudart.so.12'
 subprocess.run(s['scp']+[str(h.B/n) for n in CASES]+[str(h.B/'profile.so'),str(runtime),'ubuntu@'+s['ip']+':/tmp/steady/'],check=True)
def measure(s,phase,label,workloads=None):
 if workloads is None and os.environ.get('RODINIA_WORKLOADS'):workloads=os.environ['RODINIA_WORKLOADS'].split(',')
 for name,args in CASES.items():
  if workloads and name not in workloads:continue
  d=h.O/phase/label/s['mode']/name
  if (d/'result.json').exists():
   old=json.loads((d/'result.json').read_text());assert old['correct'] and old['returncode']==0
   print('PRESERVE',d,flush=True);continue
  d.mkdir(parents=True,exist_ok=False)
  target='/tmp/steady/'+phase+'-'+label+'-'+name
  gpu=['nvidia-smi','-i',h.GPU,'--query-gpu=uuid,pstate,clocks.sm,power.draw,temperature.gpu,memory.used','--format=csv']
  if s['mode']=='passthrough':gpu=s['ssh']+['sudo env LD_LIBRARY_PATH=/opt/flyt-evidence/driver /opt/flyt-evidence/driver/nvidia-smi --query-gpu=uuid,pstate,clocks.sm,power.draw,temperature.gpu,memory.used --format=csv']
  (d/'gpu-before.csv').write_text(subprocess.check_output(gpu,text=True))
  env={'passthrough':'env -u LD_PRELOAD LD_LIBRARY_PATH=/tmp/steady:/opt/flyt-evidence/driver','flyt':'env -u LD_PRELOAD LD_LIBRARY_PATH=/tmp/flyt-test:/tmp/steady','vmweave':'env VMWEAVE_BROKER_SOCKET=/run/vmweave/gpu.sock VMWEAVE_MIRROR_DEVICE_VA=1 VMWEAVE_TRACE_REQUESTS=0 LD_PRELOAD=/opt/vmweave/lib/libvmweave_guest.so LD_LIBRARY_PATH=/opt/vmweave/lib:/tmp/steady'}[s['mode']]
  repeats=1 if phase in ('diagnostic','profile-gate') else 2
  if phase in ('diagnostic','profile-gate'):
   preload='/tmp/steady/profile.so'+(':/opt/vmweave/lib/libvmweave_guest.so' if s['mode']=='vmweave' else '')
   env+=' LD_PRELOAD='+preload
  cmd='mkdir -p '+target+' && cd '+target+' && sudo timeout -k 5 600 '+env+' EXPERIMENT_REPEATS='+str(repeats)+' /tmp/steady/'+name+' '+shlex.join(args)
  print('START',phase,label,s['mode'],name,flush=True)
  started=time.time();p=subprocess.run(s['ssh']+[cmd],capture_output=True,text=True,timeout=630);(d/'run.log').write_text(p.stdout+p.stderr)
  (d/'gpu-after.csv').write_text(subprocess.check_output(gpu,text=True))
  rows=[json.loads(x.split('EXPERIMENT_SAMPLE ',1)[1]) for x in p.stdout.splitlines() if x.startswith('EXPERIMENT_SAMPLE ')]
  hashes=h.remote(s,'sha256sum '+target+'/output-*.bin') if p.returncode==0 else ''
  expected=json.loads((h.O/'qualification/native'/name/'result.json').read_text())['hashes']['output-02.bin']
  correct=p.returncode==0 and len(rows)==repeats+2 and len(hashes.splitlines())==repeats+2 and all(x.split()[0]==expected for x in hashes.splitlines())
  h.save(d/'result.json',{'started_unix':started,'finished_unix':time.time(),'mode':s['mode'],'workload':name,'args':args,'returncode':p.returncode,'correct':correct,'samples':rows,'hashes':hashes,'binary_sha256':h.remote(s,'sha256sum /tmp/steady/'+name)})
  if phase in ('diagnostic','profile-gate') and p.returncode==0:(d/'api-profile.json').write_text(h.remote(s,'cat '+target+'/api-profile.json'))
  print('DONE',name,p.returncode,correct,flush=True)
  if not correct:
   if s['mode']=='vmweave':
    pods=json.loads(h.k('get','pods','-n',h.NS,'-o','json'))['items']
    for pod in pods:
     if pod['metadata']['name'].startswith(s['name']) and pod['metadata']['name'].endswith('-worker'):
      (d/'worker.log').write_text(h.k('logs','-n',h.NS,pod['metadata']['name'],'--tail=300'))
   raise RuntimeError(str(d)+' correctness gate failed')
h.stage=stage
