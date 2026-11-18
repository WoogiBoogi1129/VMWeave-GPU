"""Passive per-session placement evidence; no binding or workload modification."""
from common import *
import base64
code='''import pathlib,json
out=[]
for p in pathlib.Path('/proc').glob('[0-9]*'):
 try:
  cg=(p/'cgroup').read_text();label=next((k for k,v in UIDS.items() if v in cg or v.replace('-','_') in cg),None)
  if not label:continue
  nodes={};policies={}
  for line in (p/'numa_maps').read_text().splitlines():
   fields=line.split()
   if len(fields)>1:policies[fields[1]]=policies.get(fields[1],0)+1
   for field in fields:
    if field.startswith('N') and '=' in field and field[1:field.index('=')].isdigit():
     k,v=field.split('=');nodes[k]=nodes.get(k,0)+int(v)
  status=(p/'status').read_text().splitlines()
  out.append({'pid':int(p.name),'role':label,'comm':(p/'comm').read_text().strip(),'mapped_pages_by_node':nodes,'mapping_policies':policies,'affinity':[l for l in status if l.startswith(('Cpus_allowed_list:','Mems_allowed_list:'))]})
 except (OSError,ProcessLookupError):pass
print(json.dumps(out,indent=2))
'''
while not (B/'numa.stop').exists():
 try:
  s=json.loads((B/'active.json').read_text());label=s['label'];target=O/'evidence'/(label+'-numa.json')
  hashes=O/'evidence'/(label+'-client-sha256.txt')
  if not hashes.exists():
   mode=s['mode']
   if mode=='V':
    encoded=call(s['ssh']+['sudo base64 -w0 /run/vmweave/layout.bin'])
    (O/'evidence'/(label+'-layout.bin')).write_bytes(base64.b64decode(encoded))
   libs={'N':['probe','libcudart.so.12'],'V':['probe','libvmweave_guest.so'],'F':['probe','cricket-client.so','libtirpc.so.3.0.0','flyt-client-manager'],'L':['probe','libcuda.so.1','libcudart.so.12']}[mode]
   if mode=='N':hashes.write_text(call(['sha256sum',*[B/'artifacts'/mode/f for f in libs]]))
   else:
    paths=['/opt/comm/artifacts/'+mode+'/'+f for f in libs]
    if mode=='V':paths.append('/opt/vmweave/lib/libvmweave_guest.so')
    hashes.write_text(call(s['ssh']+[shlex.join(['sha256sum',*paths])]))
  if not target.exists():
   uids={'server':s['server_uid']}
   if 'launcher_uid' in s:uids['qemu']=s['launcher_uid']
   save(target,{'utc':time.time(),'note':'Per-process numa_maps page sums; not deduplicated physical footprint. Default memory placement; no strict binding.','processes':json.loads(admin(code.replace('UIDS',repr(uids))))})
 except (OSError,ValueError,S.SubprocessError):pass
 time.sleep(5)
