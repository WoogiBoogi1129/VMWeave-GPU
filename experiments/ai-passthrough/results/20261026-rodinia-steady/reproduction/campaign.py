import subprocess,sys,json,time,os
import measure as m
h=m.h
# Each round launches a fresh VM/backend for remote modes, fresh process for Native.
# Native CUDA context must be closed before binding the GPU to passthrough.
orders=[['native','passthrough','flyt','vmweave'],['passthrough','vmweave','native','flyt'],['flyt','native','vmweave','passthrough'],['vmweave','flyt','passthrough','native'],['native','flyt','vmweave','passthrough']]
for mode in ['native','passthrough','flyt','vmweave']:
 for name in m.CASES:
  r=json.loads((h.O/'qualification'/('gate4' if name=='sc' else 'gate3' if mode=='flyt' else 'gate2')/mode/name/'result.json').read_text());assert r['correct'] and r['returncode']==0
manifest=json.loads((h.O/'manifest.json').read_text());manifest['status']='FORMAL_IN_PROGRESS';manifest['orders']=orders;h.save(h.O/'manifest.json',manifest)
for i,order in enumerate(orders,1):
 for mode in order:
  label='r'+str(i);existing=h.O/'formal'/label/mode
  complete=True
  for name in m.CASES:
   f=existing/name/'result.json'
   if not f.exists():complete=False;continue
   r=json.loads(f.read_text());assert r['correct'] and r['returncode']==0 and len(r['samples'])==4
  if complete:
   print('PRESERVE COMPLETE',label,mode,flush=True);continue
  print('START',label,mode,flush=True)
  with (h.B/(label+'-'+mode+'.log')).open('w') as f:
   env=os.environ.copy();env['RODINIA_ATTEMPT']=label+'-resume' if existing.exists() else label
   p=subprocess.run([sys.executable,str(h.B/('run-'+mode+'.py')),label],stdout=f,stderr=subprocess.STDOUT,env=env)
  if p.returncode:
   manifest['status']='FORMAL_FAILED';manifest['failed']=[label,mode];h.save(h.O/'manifest.json',manifest);sys.exit(p.returncode)
  print('DONE',label,mode,flush=True)
manifest['status']='MEASUREMENTS_COMPLETE_CLEANUP_PENDING';h.save(h.O/'manifest.json',manifest)
subprocess.run([sys.executable,str(h.B/'analyze.py')],check=True)
