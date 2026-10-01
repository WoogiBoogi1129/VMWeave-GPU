"""Post-selection default-policy VM check and two-VM start/stop smoke test."""
from runtime import *
import runtime
import concurrent.futures
final=json.loads((BASE/'final.json').read_text())
assert json.loads((OUT/'validation.json').read_text())['candidate_eligible']
runtime.IMAGES['worker']=final['worker']
def session(name,cap=100,slot='a'):
 s=Session(name,cap=cap,slot=slot);s.art=BASE/'final-artifacts';s.worker_hash=final['worker_sha256'];s.prepare();return s
if sys.argv[1]=='default':
 s=session('sf-default-both');prefix='/tmp/perf/'+s.name
 cmd=s.command('probe-S',['batch',10,10,3,prefix,'/tmp/perf/work.ptx',0,31])
 cmd[-1]=cmd[-1].replace('sudo env ','sudo env FLYT_METRICS=1 ')
 try:execute_stream(s,cmd,prefix)
 finally:s.close()
 save(OUT/'default-regression.json',{'run':s.name,'policy_overrides':False,'telemetry_enabled':True,'artifacts':final})
elif sys.argv[1]=='shared':
 a=session('sf-shared-a',50,'a');b=session('sf-shared-b',50,'b');start=time.time()+25
 save(OUT/'shared-regression-protocol.json',{'start_utc':start,'caps':[50,50],'A_s':120,'B_start_offset_s':40,'B_s':40,'warmup_s':5,'kernel_iterations':1048576,'scope':'One-pair correctness/start-stop regression. Not a quota-enforcement or statistical performance claim.'})
 try:
  with concurrent.futures.ThreadPoolExecutor(2) as pool:
   x=pool.submit(a.execute,'load',120,5,1048576,0,start)
   y=pool.submit(b.execute,'load',40,5,1048576,0,start+40)
   x.result();y.result()
 finally:
  a.close();b.close()
 save(OUT/'shared-regression-complete.json',{'runs':[a.name,b.name],'utc':time.time()})
else:raise ValueError(sys.argv[1])
