import json,subprocess,concurrent.futures
from pathlib import Path
R=Path.cwd();B=R/'.local/flyt-compatibility-20261026'
def stage(side):
 b=B/side;s=json.loads((b/'state.json').read_text());cmd=json.loads((b/'ssh.json').read_text());ssh=cmd['ssh'];scp=cmd['scp']
 bundle=R/'.local/thesis-isolation-20261012/guest-python-cuda.tgz'
 subprocess.run(scp+[str(bundle),'ubuntu@'+s['ip']+':/tmp/guest-python-cuda.tgz'],check=True)
 subprocess.run(ssh+['sudo tar -xzf /tmp/guest-python-cuda.tgz -C / && rm /tmp/guest-python-cuda.tgz'],check=True)
 subprocess.run(scp+[str(R/'experiments/thesis-isolation/probes/flyt_mps_mlp.py'),'ubuntu@'+s['ip']+':/tmp/flyt-test/mlp.py'],check=True)
 # Keep real CPU-side CUDA libraries; intercept the runtime using Flyt.
 print(side,'python staged',flush=True)
with concurrent.futures.ThreadPoolExecutor(2) as pool:list(pool.map(stage,['a','b']))
