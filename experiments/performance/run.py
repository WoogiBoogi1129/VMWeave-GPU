"""Run the preregistered campaign sequentially; concurrency only within a VM pair."""
import argparse,concurrent.futures,random
from runtime import *
from tcp_runtime import TCP
p=argparse.ArgumentParser();p.add_argument('stage',choices=['overhead','single','shared']);p.add_argument('--repetitions',default='1,2,3,4,5');a=p.parse_args()
protocol=json.loads((OUT/'protocol.json').read_text());reps=protocol['load']['iterations'];count=protocol['load']['fixed_count']
def idle():
 inventory=call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
 if GPU in inventory:raise RuntimeError('GPU already has a compute process; do not overlap independent runs: '+inventory)
def one(s,kind):
 print('SESSION_START',s.name,time.time(),flush=True)
 try:
  idle();s.prepare()
  if s.path=='T':
   prefix='/tmp/perf/'+s.name
   cmd=s.ssh+['sudo env SM_CORE='+str(s.sm)+' LD_LIBRARY_PATH=/tmp/perf /tmp/perf/probe-T batch 10 30 10 '+prefix+' /tmp/perf/work.cubin 0 127']
   execute_stream(s,cmd,prefix)
  else:s.execute(kind=kind,reps=reps,count=count if kind=='load' else 0)
 except Exception as e:save(s.out/'failure.json',{'error':str(e),'utc':time.time()});raise
 finally:s.close()
 print('SESSION_COMPLETE',s.name,time.time(),flush=True)
for rep in map(int,a.repetitions.split(',')):
 if a.stage=='overhead':
  for label in ['NTS','TSN','SNT','NST','STN'][rep-1]:
   name=f'perf-o-r{rep}-{label.lower()}'
   s=TCP(BASE,name) if label=='T' else Session(name,label)
   one(s,'overhead')
 elif a.stage=='single':
  caps=[25,50,75,100];random.Random(20260930+rep).shuffle(caps)
  for cap in caps:one(Session(f'perf-c-r{rep}-{cap}',cap=cap),'load')
 else:
  conditions=[(50,50,'a'),(50,50,'b'),(25,75,'a'),(75,25,'b')];random.Random(20260930+rep).shuffle(conditions)
  for ca,cb,slot in conditions:
   name=f'perf-d-r{rep}-{ca}-{cb}-{slot}'
   sa=Session(name+'-a',cap=ca,slot=slot);sb=Session(name+'-b',cap=cb,slot='b' if slot=='a' else 'a')
   print('PAIR_START',name,time.time(),flush=True)
   try:
    idle();sa.prepare();sb.prepare();start=time.time()+60
    save(OUT/'pairs'/(name+'.json'),{'name':name,'a':sa.name,'b':sb.name,'cap_a':ca,'cap_b':cb,'always_active_slot':slot,'scheduled_start_host_utc':start,'b_start_offset_s':60,'b_stop_offset_s':180,'end_offset_s':240})
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
     fs=[pool.submit(sa.execute,seconds=240,warmup=30,reps=reps,start=start),pool.submit(sb.execute,seconds=120,warmup=30,reps=reps,start=start+60)]
     for f in fs:f.result()
   except Exception as e:save(OUT/'pairs'/(name+'-failure.json'),{'error':str(e),'utc':time.time()});raise
   finally:
    sb.close();sa.close()
   print('PAIR_COMPLETE',name,time.time(),flush=True)
save(OUT/(a.stage+'-complete.json'),{'utc':time.time(),'repetitions':a.repetitions})
