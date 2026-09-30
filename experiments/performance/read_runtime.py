"""Read only selected GPU process fields for a specific campaign Pod UID."""
import hashlib,json,re,sys,subprocess,struct
from pathlib import Path
uid=sys.argv[1];assert re.fullmatch('[a-f0-9-]{36}',uid)
keys={'LD_PRELOAD','LD_LIBRARY_PATH','CUDA_DEVICE_SM_LIMIT','CUDA_DEVICE_SM_LIMIT_0','CUDA_DEVICE_MEMORY_LIMIT_0','GPU_CORE_UTILIZATION_POLICY','FLYT_TRACE_REQUESTS','FLYT_TRACE_CALLS','CUDA_MPS_PIPE_DIRECTORY','CUDA_MPS_ENABLE_PER_CTX_DEVICE_MULTIPROCESSOR_PARTITIONING','CUDA_MPS_ACTIVE_THREAD_PERCENTAGE'}
rows=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  cg=(p/'cgroup').read_text()
  if uid not in cg and uid.replace('-','_') not in cg:continue
  cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  if not any(x in cmd for x in ('/opt/flyt/bin/flyt-shm-worker','/evidence/probe-N','/evidence/load-N','cricket-rpc-server','nvidia-cuda-mps-server')):continue
  all_maps=(p/'maps').read_text().splitlines()
  maps=[x for x in all_maps if any(s in x for s in ('libvgpu','libcuda'))]
  env=dict(x.split('=',1) for x in (p/'environ').read_bytes().decode(errors='replace').split('\0') if '=' in x)
  files={x.split()[-1] for x in maps if x.split()[-1].startswith('/')}
  rows.append({'pid':int(p.name),'executable_sha256':hashlib.sha256((p/'exe').read_bytes()).hexdigest(),'command':cmd,'maps':maps,'environment':{k:env.get(k) for k in sorted(keys)},'library_hashes':{f:hashlib.sha256((p/'root'/f.lstrip('/')).read_bytes()).hexdigest() for f in files},'affinity_status':[s for s in (p/'status').read_text().splitlines() if s.startswith(('Cpus_allowed_list','Mems_allowed_list'))]})
 except (FileNotFoundError,ProcessLookupError):continue
for row in rows:
 try:
  pid=row['pid'];p=Path('/proc')/str(pid);exe=str((p/'exe').resolve());maps=(p/'maps').read_text().splitlines()
  elf=(p/'exe').read_bytes();pie=struct.unpack_from('<H',elf,16)[0]==3
  base=min(int(x.split('-')[0],16)-int(x.split()[2],16) for x in maps if x.split()[-1]==exe) if pie else 0
  rel=subprocess.check_output(['chroot','/host','/usr/bin/readelf','-Wr','/proc/'+str(pid)+'/exe'],text=True)
  symbols={}
  for line in rel.splitlines():
   cols=line.split()
   if 'JUMP_SLOT' not in line or len(cols)<5 or cols[4].split('@')[0] not in ['cuLaunchKernel','cudaMemcpy','cudaDeviceSynchronize']:continue
   address=base+int(cols[0],16)
   with (p/'mem').open('rb',buffering=0) as memory:
    memory.seek(address);target=struct.unpack('<Q',memory.read(8))[0]
   owner=next((x.split()[-1] for x in maps if int(x.split()[0].split('-')[0],16)<=target<int(x.split()[0].split('-')[1],16)),'unmapped')
   symbols[cols[4]]={'got_address':hex(address),'resolved_address':hex(target),'mapped_object':owner}
  row['resolved_plt_symbols']=symbols
 except Exception as e:row['symbol_resolution_error']=str(e)
if not rows:raise RuntimeError('No matching GPU process')
print(json.dumps(rows))
