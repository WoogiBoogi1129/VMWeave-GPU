import subprocess,json,hashlib,os
from pathlib import Path
R=Path.cwd();B=R/'.local/rodinia-steady-20261026';O=R/'experiments/ai-passthrough/results/20261026-rodinia-steady/qualification/native'
cases={'nw':['2048','10'],'lu':['-s','2064'],'srad':['2048','2048','0','127','0','127','0.5','2'],'sc':['10','20','256','65536','65536','1000','none','output.txt','1']}
env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='GPU-772181af-05a4-0c24-de59-8487bd37c142',LD_LIBRARY_PATH=str(R/'.local/thesis-isolation-20261012/bundle-stage/opt/flyt-cuda-libs'),EXPERIMENT_REPEATS='2')
for name,args in cases.items():
 d=O/name;d.mkdir(parents=True,exist_ok=True);print('START',name,flush=True)
 with (d/'run.log').open('w') as f:
  try:p=subprocess.run(['taskset','-c','32-39',str(B/name),*args],cwd=d,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=300);rc=p.returncode
  except subprocess.TimeoutExpired:rc=124
 rows=[json.loads(x.split('EXPERIMENT_SAMPLE ',1)[1]) for x in (d/'run.log').read_text().splitlines() if x.startswith('EXPERIMENT_SAMPLE ')]
 hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in d.glob('output*') if p.is_file()}
 (d/'result.json').write_text(json.dumps({'returncode':rc,'args':args,'samples':rows,'hashes':hashes},indent=2));print(name,rc,rows,hashes,flush=True)
