"""Read only selected GPU process fields for a specific campaign Pod UID."""
import hashlib,json,re,sys
from pathlib import Path
uid=sys.argv[1];assert re.fullmatch('[a-f0-9-]{36}',uid)
keys={'LD_PRELOAD','LD_LIBRARY_PATH','CUDA_DEVICE_SM_LIMIT','CUDA_DEVICE_SM_LIMIT_0','CUDA_DEVICE_MEMORY_LIMIT_0','GPU_CORE_UTILIZATION_POLICY'}
rows=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  cg=(p/'cgroup').read_text()
  if uid not in cg and uid.replace('-','_') not in cg:continue
  cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  if not any(x in cmd for x in ('/opt/flyt/bin/flyt-shm-worker','/evidence/campaign-probe-native')):continue
  maps=[x for x in (p/'maps').read_text().splitlines() if any(s in x for s in ('libvgpu','libcuda'))]
  env=dict(x.split('=',1) for x in (p/'environ').read_bytes().decode(errors='replace').split('\0') if '=' in x)
  files={x.split()[-1] for x in maps if x.split()[-1].startswith('/')}
  rows.append({'pid':int(p.name),'command':cmd,'maps':maps,'environment':{k:env.get(k) for k in sorted(keys)},'library_hashes':{f:hashlib.sha256((p/'root'/f.lstrip('/')).read_bytes()).hexdigest() for f in files},'affinity_status':[s for s in (p/'status').read_text().splitlines() if s.startswith(('Cpus_allowed_list','Mems_allowed_list'))]})
 except (FileNotFoundError,ProcessLookupError):continue
if not rows:raise RuntimeError('No matching GPU process')
print(json.dumps(rows))
