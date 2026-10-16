"""Sample process CPU counters for exact Pod UIDs; pid starttime detects reuse."""
import json,pathlib,sys,time,os
seen=set()
uids=sys.argv[1:];hz=os.sysconf('SC_CLK_TCK')
while True:
 rows=[]
 for p in pathlib.Path('/proc').glob('[0-9]*'):
  try:
   cg=(p/'cgroup').read_text();uid=next((u for u in uids if u in cg or u.replace('-','_') in cg),None)
   if not uid:continue
   st=(p/'stat').read_text().rsplit(')',1)[1].split()
   identity=(p.name,st[19])
   if identity not in seen:
    seen.add(identity)
    cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
    if 'flyt-shm' in cmd and 'qemu' not in cmd:
     env=dict(x.split('=',1) for x in (p/'environ').read_text().split('\0') if '=' in x)
     print(json.dumps({'event':'worker_identity','utc':time.time(),'pod_uid':uid,'pid':int(p.name),'command':cmd,'environment':{k:v for k,v in env.items() if k.startswith(('CUDA_DEVICE','GPU_CORE','LIBCUDA_LOG','FLYT_RESOURCE'))},'libraries':sorted(set(x.split()[-1] for x in (p/'maps').read_text().splitlines() if 'libvgpu' in x or 'libcuda' in x))}),flush=True)
   rows.append({'pod_uid':uid,'pid':int(p.name),'start_ticks':int(st[19]),'cpu_seconds':(int(st[11])+int(st[12]))/hz})
  except (OSError,ValueError):pass
 try:print(json.dumps({'utc':time.time(),'processes':rows}),flush=True)
 except BrokenPipeError:break
 time.sleep(1)
