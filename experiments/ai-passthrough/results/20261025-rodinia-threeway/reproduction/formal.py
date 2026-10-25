import subprocess,sys,json,time
import rodinia_campaign as h
# All qualification gates must pass before any formal sample.
for path in [h.O/'qualification/flyt/result.json',h.O/'qualification/gate/passthrough/result.json',h.O/'qualification/gate/vmweave/result.json']:
 rows=json.loads(path.read_text());assert len(rows)==2 and all(x['returncode']==0 and x.get('correct',x.get('matches_native_reference',False)) for x in rows)
manifest=json.loads((h.O/'manifest.json').read_text());manifest['formal_runs']=sum(len(json.loads(p.read_text())) for p in (h.O/'formal').glob('*/*/result.json'));manifest['status']='FORMAL_IN_PROGRESS';h.save(h.O/'manifest.json',manifest)
for i,order in enumerate([['passthrough','flyt','vmweave'],['flyt','vmweave','passthrough'],['vmweave','passthrough','flyt']],1):
 for mode in order:
  label='r'+str(i);log=h.O/('formal-'+label+'-'+mode+'.log');script={'passthrough':'native-run.py','flyt':'flyt-run.py','vmweave':'vmw-run.py'}[mode]
  if (h.O/'formal'/label/mode/'result.json').exists():
   existing=json.loads((h.O/'formal'/label/mode/'result.json').read_text());assert len(existing)==2 and all(x['returncode']==0 and x.get('correct',x.get('matches_native_reference',False)) for x in existing);print('PRESERVE COMPLETED',label,mode,flush=True);continue
  print('START',label,mode,flush=True)
  with log.open('w') as f:p=subprocess.run([sys.executable,str(h.B/script),label],stdout=f,stderr=subprocess.STDOUT)
  if p.returncode:
   manifest['status']='FORMAL_FAILED';manifest['failed_stage']=[label,mode];h.save(h.O/'manifest.json',manifest);raise RuntimeError(str(log))
  manifest['formal_runs']+=2;h.save(h.O/'manifest.json',manifest);print('DONE',manifest['formal_runs'],'/18',flush=True)
subprocess.run([sys.executable,str(h.B/'analyze.py')],check=True)
manifest['status']='MEASUREMENTS_COMPLETE_CLEANUP_PENDING';h.save(h.O/'manifest.json',manifest)
