import sys,json,importlib.util,shutil
from pathlib import Path
R=Path.cwd();B=R/'.local/rodinia-threeway-20261025';O=R/'experiments/ai-passthrough/results/20261025-rodinia-threeway'
p=R/'experiments/ai-passthrough/results/20261022-sgemm-bestcase/run.py';spec=importlib.util.spec_from_file_location('run',p);r=importlib.util.module_from_spec(spec);sys.modules['run']=r;spec.loader.exec_module(r)
r.BASE=r.native.BASE=r.old.BASE=B;r.OUT=r.native.OUT=r.old.OUT=O;r.c.OUT=r.s.OUT=O/'audit';r.c.HELPER=r.s.HELPER='rodinia-native-admin-1025';r.c.ADMIN=json.loads((R/'deploy/releases/v0.5.3.json').read_text())['images']['worker']
for n in ['small','medium','large']:
 q=B/(n+'.pt')
 if not q.exists():q.symlink_to(R/'.local/sgemm-bestcase-20261022'/(n+'.pt'))
r.c.ensure_admin()
for args,file in [(('get','ds','hami-device-plugin','-n','kube-system','-o','json'),'hami-ds-before.json'),(('get','ds','nvidia-dcgm-exporter','-n','gpu-operator','-o','json'),'dcgm-ds-before.json'),(('get','kubevirt','-A','-o','json'),'kubevirt-before.json')]:
 if not (B/file).exists():(B/file).write_text(r.c.k(*args))
source=Path(p).read_text();start=source.index('def bootstrap():');end=source.index('\ndef run(',start);part=source[start:end].replace('sgemm-bestcase-20261022','rodinia-threeway-20261025').replace('ai-sgemm-native','rodinia-native-1025');exec(part,r.__dict__)
if __name__=='__main__':r.bootstrap()
