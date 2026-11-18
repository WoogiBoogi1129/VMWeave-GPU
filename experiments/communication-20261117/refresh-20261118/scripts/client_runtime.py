import pathlib,json,hashlib
rows=[]
for p in pathlib.Path('/proc').glob('[0-9]*'):
 try:
  if (p/'comm').read_text().strip()!='probe':continue
  env=dict(x.split('=',1) for x in (p/'environ').read_text().split('\0') if '=' in x)
  paths=sorted(set(l.split()[-1] for l in (p/'maps').read_text().splitlines() if 'libvmweave_guest.so' in l))
  rows.append({'pid':int(p.name),'environment':{k:v for k,v in env.items() if k.startswith('VMWEAVE_') or k=='LD_LIBRARY_PATH'},'libraries':{f:hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest() for f in paths}})
 except (OSError,ProcessLookupError):pass
print(json.dumps(rows,indent=2))
