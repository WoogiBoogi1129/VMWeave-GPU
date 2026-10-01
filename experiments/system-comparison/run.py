"""Sequential whole-system pairs; fresh VM/processes for every repetition."""
from runtime import *
from tcp_runtime import TCP
import random

def one(name,path,seconds,warmup,shift):
 inventory=call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
 assert GPU not in inventory,'Do not overlap GPU measurements: '+inventory
 s=TCP(BASE,name) if path=='T' else Session(name)
 save(s.out/'condition.json',{'path':path,'seconds':seconds,'warmup_min_s':warmup,'shift':shift,'metrics':False})
 print('SESSION_START',name,time.time(),flush=True)
 try:
  s.prepare();prefix='/tmp/perf/'+name
  if path=='T':cmd=s.ssh+['sudo env SM_CORE='+str(s.sm)+' LD_LIBRARY_PATH=/tmp/perf /tmp/perf/probe-T batch '+shlex.join(list(map(str,[seconds,seconds,warmup,prefix,'/tmp/perf/work.cubin',shift,255])))]
  else:cmd=s.command('probe-S',['batch',seconds,seconds,warmup,prefix,'/tmp/perf/work.ptx',shift,255])
  result=execute_stream(s,cmd,prefix);assert len(result)==8
 except Exception as e:
  save(s.out/'failure.json',{'utc':time.time(),'error':str(e)});raise
 finally:s.close()
 print('SESSION_COMPLETE',name,time.time(),flush=True)

stage=sys.argv[1];ensure_admin()
save(OUT/('environment-'+stage+'.json'),{'source_commit':call(['git','rev-parse','HEAD']).strip(),'gpu':call(['nvidia-smi','-q']),'started_utc':time.time()})
if stage in ['pilot','pilot-ready']:
 for path in ['T','S']:one('sc-'+stage+'-'+path.lower(),path,3,2,0)
elif stage=='formal':
 protocol=json.loads((OUT/'protocol.json').read_text())
 for name,expected in protocol['artifact_hashes'].items():
  p=BASE/'artifacts'/('bin/flyt-shm-worker' if name=='flyt-shm-worker' else name)
  assert hashlib.sha256(p.read_bytes()).hexdigest()==expected,name
 for pair in protocol['pairs']:
  for path in pair['order']:
   name='sc-r'+str(pair['repeat'])+'-'+path.lower();p=OUT/'runs'/name
   if (p/'cleanup.json').exists():
    assert json.loads((p/'execution.json').read_text())['exit_code']==0 and not (p/'failure.json').exists();continue
   assert not p.exists(),'Preserve and review incomplete attempt '+name
   one(name,path,60,10,pair['shift'])
 save(OUT/'formal-complete.json',{'utc':time.time(),'sessions':10,'windows':80})
else:raise ValueError(stage)
