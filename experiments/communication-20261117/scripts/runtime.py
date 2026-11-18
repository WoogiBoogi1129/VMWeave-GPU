"""Read only target Pod processes. No whole-node environments/credentials."""
import pathlib,json,hashlib,sys
uids=json.loads(sys.argv[1]);rows=[]
keys=['CUDA_DEVICE_SM_LIMIT','CUDA_DEVICE_MEMORY_LIMIT','CUDA_DEVICE_MEMORY_SHARED_CACHEFILE','LD_PRELOAD','LD_LIBRARY_PATH','CUDA_VISIBLE_DEVICES','NVIDIA_VISIBLE_DEVICES','GPU_CORE_UTILIZATION_POLICY','CUDA_MPS_PIPE_DIRECTORY','CUDA_MPS_ACTIVE_THREAD_PERCENTAGE','VMWEAVE_BULK_COPY','VMWEAVE_PINNED_POOL','VMWEAVE_SESSION_ARENA','VMWEAVE_SESSION_EVENTFD','VMWEAVE_BROKER_SOCKET','LUPINE_SERVER']
for p in pathlib.Path('/proc').glob('[0-9]*'):
 try:
  cg=(p/'cgroup').read_text();label=next((l for l,u in uids.items() if u in cg or u.replace('-','_') in cg),None)
  if label is None:continue
  libs=sorted(set(line.split()[-1] for line in (p/'maps').read_text().splitlines() if '/' in line and any(t in line for t in ['libcuda','libvgpu','libvmweave','cricket','lupine','libflyt'])))
  if not libs:continue
  env=dict(x.split('=',1) for x in (p/'environ').read_text().split('\0') if '=' in x)
  hashes={}
  for path in libs:
   try:hashes[path]=hashlib.sha256((p/'root'/path.lstrip('/')).read_bytes()).hexdigest()
   except OSError:hashes[path]=None
  rows.append({'label':label,'pid':int(p.name),'comm':(p/'comm').read_text().strip(),'cpuset':next(l for l in (p/'status').read_text().splitlines() if l.startswith('Cpus_allowed_list:')),'libraries':hashes,'environment':{k:env[k] for k in keys if k in env}})
 except (OSError,ProcessLookupError):pass
print(json.dumps(rows,indent=2))
