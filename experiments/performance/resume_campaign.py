"""Resume only missing shared conditions, preserving the interrupted attempt."""
import concurrent.futures,random,urllib.request
from runtime import *
protocol=json.loads((OUT/'protocol.json').read_text())
interruptions=json.loads((OUT/'interruptions.json').read_text())
replacement={r['pair']:r['replacement_pair'] for r in interruptions}
assert not (OUT/'campaign-execution-complete.json').exists()
for name,expected in protocol['artifact_sha256'].items():
 assert hashlib.sha256((BASE/'artifacts'/name).read_bytes()).hexdigest()==expected,('Frozen artifact changed',name)
save(OUT/'shared-resume1-source.json',{'utc':time.time(),'pid':os.getpid(),'commit':call(['git','rev-parse','HEAD']).strip(),'source_diff':call(['git','diff','--','experiments/performance']),'source_sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in Path(__file__).parent.iterdir() if f.suffix in ['.py','.c','.sh']},'protocol_sha256':hashlib.sha256((OUT/'protocol.json').read_bytes()).hexdigest(),'interruptions':interruptions})
(OUT/'resume1-gpu-before.txt').write_text(call(['nvidia-smi','-q']))
mon=json.loads((BASE/'monitor.json').read_text())
executed=[];preserved=[]
try:
 for rep in range(1,6):
  conditions=[tuple(c) for c in protocol['shared']['conditions']];random.Random(20260930+rep).shuffle(conditions)
  for ca,cb,slot in conditions:
   original=f'perf-d-r{rep}-{ca}-{cb}-{slot}'
   folders=[OUT/'runs'/(original+'-'+role) for role in ['a','b']]
   if all((f/'execution.json').exists() and (f/'cleanup.json').exists() and not (f/'failure.json').exists() for f in folders):
    preserved.append(original);print('PRESERVED_COMPLETE_PAIR',original,flush=True);continue
   if any(f.exists() for f in folders):
    assert original in replacement and all((f/'interruption.json').exists() for f in folders),'Undocumented incomplete attempt'
    name=replacement[original]
   else:name=original
   assert GPU not in call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
   targets=json.load(urllib.request.urlopen(mon['prometheus']+'/api/v1/targets',timeout=10))['data']['activeTargets']
   assert len(targets)==4 and all(t['health']=='up' for t in targets),'Monitoring not ready'
   sa=Session(name+'-a',cap=ca,slot=slot);sb=Session(name+'-b',cap=cb,slot='b' if slot=='a' else 'a')
   print('PAIR_START',name,time.time(),flush=True)
   try:
    sa.prepare();sb.prepare();start=time.time()+60
    save(OUT/'pairs'/(name+'.json'),{'name':name,'a':sa.name,'b':sb.name,'cap_a':ca,'cap_b':cb,'always_active_slot':slot,'scheduled_start_host_utc':start,'b_start_offset_s':60,'b_stop_offset_s':180,'end_offset_s':240,'logical_condition':original,'resume_block':'resume1'})
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
     fs=[pool.submit(sa.execute,seconds=240,warmup=30,reps=protocol['load']['iterations'],start=start),pool.submit(sb.execute,seconds=120,warmup=30,reps=protocol['load']['iterations'],start=start+60,hold_until=start+250)]
     for future in fs:future.result()
   except BaseException as e:
    save(OUT/'pairs'/(name+'-failure.json'),{'error':repr(e),'utc':time.time()});raise
   finally:
    sb.close();sa.close()
   executed.append(name);print('PAIR_COMPLETE',name,time.time(),flush=True)
 save(OUT/'shared-complete.json',{'utc':time.time(),'preserved_pairs':preserved,'resumed_pairs':executed,'interrupted_attempts':interruptions})
 commands=[['python3','experiments/performance/export_telemetry.py'],['taskset','-c','48-51','.local/evidence-venv/bin/python','experiments/performance/verify.py',str(OUT)],['taskset','-c','48-51','.local/evidence-venv/bin/python','experiments/performance/analyze.py',str(OUT)],['taskset','-c','48-51','.local/evidence-venv/bin/python','experiments/performance/plot.py',str(OUT)],['python3','experiments/performance/annotate_grafana.py'],['taskset','-c','48-51','node','experiments/performance/capture_grafana.cjs',str(OUT),str(BASE),'d']]
 for i,cmd in enumerate(commands):
  print('COLLECT',i,time.time(),flush=True)
  with (BASE/f'collect-d-{i}.txt').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True,env={**os.environ,'NODE_PATH':str(ROOT/'.local/evidence-20260924/tools/node_modules')})
 assert json.loads((OUT/'validation.json').read_text())['campaign_complete']
 save(OUT/'campaign-execution-complete.json',{'utc':time.time(),'stages':['overhead','single','shared'],'status':'Completed valid repetitions with one explicitly retained interrupted pre-measurement attempt; see enforcement separately.'})
 print('CAMPAIGN_EXECUTION_COMPLETE',time.time(),flush=True)
except BaseException as e:
 save(OUT/'resume1-failure.json',{'utc':time.time(),'error':repr(e)});raise
