import sys,subprocess,json,hashlib,os,time
from pathlib import Path
import measure as m
h=m.h;label=sys.argv[1];profile_gate='--profile-gate' in sys.argv;diagnostic='--diagnostic' in sys.argv or profile_gate
env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES=h.GPU,LD_LIBRARY_PATH=str(h.R/'.local/thesis-isolation-20261012/bundle-stage/opt/flyt-cuda-libs'),EXPERIMENT_REPEATS='1' if diagnostic else '2')
env.pop('LD_PRELOAD',None)
if diagnostic:env['LD_PRELOAD']=str(h.B/'profile.so')
for name,args in m.CASES.items():
 if os.environ.get('RODINIA_WORKLOADS') and name not in os.environ['RODINIA_WORKLOADS'].split(','):continue
 if profile_gate and name!="nw":continue
 assert hashlib.sha256((h.B/name).read_bytes()).hexdigest()==json.loads((h.O/'manifest.json').read_text())['binaries'][name]
 d=h.O/('profile-gate' if profile_gate else 'diagnostic' if diagnostic else 'qualification' if label.startswith('gate') else 'formal')/label/'native'/name
 if (d/'result.json').exists():
  old=json.loads((d/'result.json').read_text());assert old['correct'] and old['returncode']==0
  print('PRESERVE',d,flush=True);continue
 d.mkdir(parents=True,exist_ok=False)
 gpu=['nvidia-smi','-i',h.GPU,'--query-gpu=uuid,pstate,clocks.sm,power.draw,temperature.gpu,memory.used','--format=csv'];(d/'gpu-before.csv').write_text(subprocess.check_output(gpu,text=True))
 started=time.time();p=subprocess.run(['taskset','-c','32-39',str(h.B/name),*args],cwd=d,env=env,capture_output=True,text=True,timeout=330);(d/'run.log').write_text(p.stdout+p.stderr)
 (d/'gpu-after.csv').write_text(subprocess.check_output(gpu,text=True))
 samples=[json.loads(x.split('EXPERIMENT_SAMPLE ',1)[1]) for x in p.stdout.splitlines() if x.startswith('EXPERIMENT_SAMPLE ')]
 hashes={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in d.glob('output-*.bin')};expected=json.loads((h.O/'qualification/native'/name/'result.json').read_text())['hashes']['output-02.bin'];correct=p.returncode==0 and len(samples)==(3 if diagnostic else 4) and len(hashes)==(3 if diagnostic else 4) and all(x==expected for x in hashes.values())
 h.save(d/'result.json',{'started_unix':started,'finished_unix':time.time(),'binary_sha256':hashlib.sha256((h.B/name).read_bytes()).hexdigest(),'mode':'native','workload':name,'args':args,'returncode':p.returncode,'correct':correct,'samples':samples,'hashes':hashes});print(name,correct,flush=True);assert correct

if label=="r5" and not diagnostic:subprocess.run([sys.executable,__file__,label,"--diagnostic"],check=True)

if label=="r3" and not diagnostic:subprocess.run([sys.executable,__file__,label,"--profile-gate"],check=True)
