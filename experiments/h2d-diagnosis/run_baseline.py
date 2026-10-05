from runtime import *
from tcp_runtime import TCP
ensure_admin()
for rep in range(1,6):
 for path in (['T','S'] if rep%2 else ['S','T']):
  name=f'hd-base-v2-r{rep}-{path.lower()}'
  if (OUT/'runs'/name/'cleanup.json').exists():continue
  assert GPU not in call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
  s=TCP(BASE,name) if path=='T' else Session(name)
  save(s.out/'condition.json',{'phase':'baseline','repeat':rep,'path':path,'seconds':60,'warmup_min_s':10,'probe':'unchanged original','bytes':16777216})
  print('START',name,flush=True)
  try:
   s.prepare();prefix='/tmp/perf/'+name
   args=['batch',60,60,10,prefix,'/tmp/perf/work.cubin' if path=='T' else '/tmp/perf/work.ptx',0,128]
   cmd=s.ssh+['sudo env SM_CORE='+str(s.sm)+' LD_LIBRARY_PATH=/tmp/perf /tmp/perf/probe-T '+shlex.join(list(map(str,args)))] if path=='T' else s.command('probe-S',args)
   assert len(execute_stream(s,cmd,prefix))==1
  except Exception as e:save(s.out/'failure.json',{'error':str(e),'utc':time.time()});raise
  finally:s.close()
  print('COMPLETE',name,flush=True)
save(OUT/'baseline-complete.json',{'repeats':5,'sessions':10})
