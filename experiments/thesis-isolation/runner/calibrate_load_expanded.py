"""Single VM, same 2GiB/50% profile; bounded load-size and submission-batch sweep."""
from e2 import *
import fcntl,hashlib
lock=(BASE/'calibrate-load.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
name='iso-load-wide-'+time.strftime('%Y%m%d%H%M%S',time.gmtime());out=OUT/name;out.mkdir();s=None;p=None;monitor=None;records=[]
cases=[(mode,size,batch) for mode,sizes in [('memory',[512,768,1024]),('compute',[4096,6144,8192])] for batch in [8,32,128] for size in sizes]
save(out/'protocol.json',{'scope':'Single-VM calibration, not contention repetitions','memory_mib':2048,'compute_percent':50,'seconds_each':30,'cases':cases,'gpu':GPU,'source_commit':call(['git','rev-parse','HEAD']).strip(),'metrics_note':'Logical byte throughput is not measured DRAM bandwidth; FLOP rate is estimated from matrix dimensions. Whole-GPU utilization under a 50% profile does not prove physical saturation.','auto_start_full_experiment':False,'max_load_buffer_mib':1024,'max_matrix_buffers_mib':768,'prior_run':'iso-load-cal-20261013104444','limitations':'Submission batching reduces explicit synchronization but not per-call forwarding overhead. No saturation claim from utilization alone.'})
save(out/'probe-hash.json',{'sha256':hashlib.sha256((ROOT/'experiments/thesis-isolation/probes/load_calibration_expanded.py').read_bytes()).hexdigest()})
print('OUTPUT',out,flush=True)
try:
 save(out/'status.json',{'state':'PREPARING','utc':time.time()});validate()
 assert GPU not in call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
 s=Session(name+'-a',slot='a',memory=2048,cap=50);s.prepare();p=MLP(s,source='load_calibration_expanded.py');freeze(s)
 with (out/'gpu-samples.csv').open('w') as telemetry,(out/'gpu-samples-stderr.txt').open('w') as err:
  monitor=subprocess.Popen(['nvidia-smi','-i',GPU,'--query-gpu=timestamp,uuid,utilization.gpu,utilization.memory,memory.used,power.draw,clocks.sm,clocks.mem','--format=csv','-l','1'],stdout=telemetry,stderr=err)
  time.sleep(5)
  for index,(mode,size,batch) in enumerate(cases):
   save(out/'status.json',{'state':'MEASURING','case':index+1,'total':len(cases),'mode':mode,'size':size,'batch':batch,'utc':time.time()})
   start=time.time();rows=p.command(f'load {mode} 30 {size} {batch}',130);end=time.time();save(out/f'case-{index+1:02d}.json',rows)
   done=rows[-1];assert done['op']=='load' and done['elapsed_s']>=30 and done['completed_kernels']>0
   records.append({'case':index+1,'mode':mode,'size':size,'batch':batch,'start_utc':start,'end_utc':end,**done,'logical_work_per_second':done['completed_kernels']*done['logical_work_per_kernel']/done['elapsed_s']})
   save(out/'results.json',records);print('CASE_COMPLETE',mode,size,batch,flush=True)
   time.sleep(3)
  assert monitor.poll() is None,'GPU telemetry process exited early'
 save(out/'status.json',{'state':'MEASUREMENT_COMPLETE','cases':len(records),'selection':'Pending comparison of size/batch scaling and telemetry; no saturation claim yet','utc':time.time()})
except Exception as e:
 save(out/'failure.json',{'error':str(e),'utc':time.time()});save(out/'status.json',{'state':'STOPPED','error':str(e),'utc':time.time()});print('ERROR',str(e),flush=True)
finally:
 if monitor and monitor.poll() is None:monitor.terminate();monitor.wait(timeout=10)
 if p:
  try:p.close()
  except Exception as e:save(out/'probe-close-error.json',{'error':str(e)})
 if s:
  try:s.close()
  except Exception as e:save(out/'cleanup-error.json',{'error':str(e)})
 save(out/'closed.json',{'utc':time.time()})
