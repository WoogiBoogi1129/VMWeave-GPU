"""User-selected original stage 5: one direction, three fixed-duration conditions."""
from e2 import *
parser=argparse.ArgumentParser();parser.add_argument('--name',required=True);parser.add_argument('--direction',choices=['ab','ba'],required=True);parser.add_argument('--seed',type=int,required=True);args=parser.parse_args()
name=args.name
out=OUT/'pairs'/name;out.mkdir(parents=True,exist_ok=False)
sessions=[];probes=[];results=[]
order=['baseline','memory','compute'];random.Random(args.seed).shuffle(order)
seconds=1260
save(out/'protocol.json',{'scope':'Original performance step 5, not renumbered isolation E2','direction':args.direction,'order':order,'seed':args.seed,'seconds_each':seconds,'sample_target':10000,'repetitions':1,'stage6_started':True,'latency_scope':'GPU forward+sync; throughput includes correctness checking','timeout_s':40,'host_completion_grace_s':100})
print('OUTPUT',out,flush=True)
try:
 validate()
 inventory=call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
 if GPU in inventory:raise RuntimeError('Test GPU is still in use')
 for slot in ['a','b']:
  s=Session(name+'-'+slot,slot=slot,memory=2048,cap=50);sessions.append(s)
  s.prepare();p=MLP(s);probes.append(p);freeze(s)
 a,b=probes if args.direction=='ab' else list(reversed(probes))
 for condition in order:
  save(out/'status.json',{'state':'MEASURING','condition':condition,'started_utc':time.time(),'seconds':seconds,'completed_conditions':len(results)})
  print('CONDITION_START',condition,time.time(),flush=True)
  if condition!='baseline':
   b.p.stdin.write(f'load {condition} {seconds+10}\n');b.p.stdin.flush()
   started=b.until('load_started',60);save(out/(condition+'-load-start.json'),started)
  observed=a.command(f'observe {seconds}',seconds+100)
  save(out/(condition+'-observer.json'),observed)
  req=[r for r in observed if r['event']=='request'];done=observed[-1]
  if condition!='baseline':
   load=b.until('done',110);save(out/(condition+'-load.json'),load)
   assert load[-1].get('completed_kernels',0)>0
  assert req and done['attempts']==len(req)
  codes=[r['code'] for r in req];latencies=sorted(r['latency_s'] for r in req if r['code']==0)
  result={'condition':condition,'attempts':len(req),'successful':len(latencies),'errors':sum(c>0 for c in codes),'mismatches':codes.count(-1),'elapsed_s':done['elapsed_s'],'throughput_rps':len(latencies)/done['elapsed_s'],'p99_s':latencies[math.ceil(.99*len(latencies))-1] if latencies else None,'sample_target_met':len(latencies)>=10000}
  results.append(result);save(out/'results.json',results);print('CONDITION_COMPLETE',json.dumps(result),flush=True)
  if any(c!=0 for c in codes):raise RuntimeError('Request failure; preserving evidence and stopping')
  assert done['elapsed_s']>=seconds
  time.sleep(5)
 base=next(r for r in results if r['condition']=='baseline')
 for r in results:
  r['throughput_retention']=r['throughput_rps']/base['throughput_rps'];r['p99_ratio']=r['p99_s']/base['p99_s']
 save(out/'results.json',results)
 save(out/'status.json',{'state':'MEASUREMENT_COMPLETE','completed_conditions':3,'service_suitability':'INCONCLUSIVE','note':'One direction and one set only; independent repetitions belong to stage 6. Fewer than 10000 observations limits tail precision; request correlation also matters.','utc':time.time()})
except Exception as e:
 save(out/'failure.json',{'error':str(e),'utc':time.time()});print('STAGE5_ERROR',str(e),flush=True)
 raise
finally:
 for p in probes:
  try:p.close()
  except Exception as e:print('CLOSE_ERROR',str(e),flush=True)
 for s in sessions:
  try:s.close()
  except Exception as e:save(s.out/'cleanup-error.json',{'error':str(e)})
 save(out/'closed.json',{'utc':time.time()})
