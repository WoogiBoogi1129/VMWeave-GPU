from runtime import *
import runtime
from tcp_runtime import TCP
variants=json.loads((BASE/'variants.json').read_text())
def one(name,variant,metrics=True,mode='sweep',seconds=60,warmup=10,path='S',size=16777216):
 assert GPU not in call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
 s=TCP(BASE,name) if path=='T' else Session(name)
 save(s.out/'condition.json',{'phase':'diagnostic','variant':variant,'metrics':metrics,'mode':mode,'seconds':seconds,'warmup_min_s':warmup,'path':path,'bytes':size})
 print('START',name,flush=True)
 log=None;stream=None
 try:
  if path=='S':
   runtime.IMAGES['worker']=json.loads((BASE/'images.json').read_text())['worker'] if variant=='stock' else variants[variant if metrics else variant+'-off']
  s.prepare()
  files=[BASE/'diagnostic'/('probe-'+path)]
  if path=='S' and variant!='stock':files.append(BASE/'diagnostic/libflyt_guest.so')
  call(s.scp+list(map(str,files))+['ubuntu@'+s.ip+':/tmp/perf/'])
  names=['probe-'+path,'libflyt_guest.so' if path=='S' else 'cricket-client.so']
  effective=call(s.ssh+['sha256sum '+' '.join('/tmp/perf/'+n for n in names)])
  (s.out/'guest-effective-hashes.txt').write_text(effective)
  for line in effective.splitlines():
   digest,file=line.split(maxsplit=1);name=Path(file).name
   local=BASE/'diagnostic'/name if name.startswith('probe-') or (name=='libflyt_guest.so' and variant!='stock') else BASE/'artifacts'/name
   assert digest==hashlib.sha256(local.read_bytes()).hexdigest(),name
  s.worker_hash=hashlib.sha256((BASE/('artifacts/bin/flyt-shm-worker' if variant=='stock' else 'diagnostic/bin/flyt-shm-worker')).read_bytes()).hexdigest()
  if path=='S':
   # Images differ only in settings; turn off metrics with a separate image when requested.
   stream=(s.out/'worker-stream.txt').open('w');log=subprocess.Popen(['kubectl','logs','-f','-n',NS,s.worker],stdout=stream,stderr=subprocess.STDOUT)
  prefix='/tmp/perf/'+name
  args=[mode,size,seconds,warmup,prefix if mode=='sweep' else prefix+'-'+mode+'-'+str(size),'/tmp/perf/work.cubin' if path=='T' else '/tmp/perf/work.ptx']
  if path=='T':cmd=s.ssh+['sudo env SM_CORE='+str(s.sm)+' LD_LIBRARY_PATH=/tmp/perf /tmp/perf/probe-T '+shlex.join(list(map(str,args)))]
  else:
   cmd=s.command('probe-S',args);cmd[-1]=cmd[-1].replace('sudo env ','sudo env HD_METRICS='+str(int(metrics))+' HD_VARIANT='+variant+' ')
  result=execute_stream(s,cmd,prefix)
  assert len(result)==(4 if mode=='sweep' else 1)
  if log:
   try:log.wait(timeout=30)
   except subprocess.TimeoutExpired:log.terminate();log.wait()
 except Exception as e:save(s.out/'failure.json',{'utc':time.time(),'error':str(e)});raise
 finally:
  if log and log.poll() is None:log.terminate();log.wait()
  if stream:stream.close()
  s.close()
 print('COMPLETE',name,flush=True)
if __name__=='__main__':
 ensure_admin()
 phase=sys.argv[1]
 if phase=='pilot':one('hd-pilot-ready-original','original',seconds=3,warmup=2)
 elif phase=='formal':
  for r in range(1,6):
   for v in (['original','reuse','pinned'] if r%2 else ['pinned','reuse','original']):
    name=f'hd-diag-r{r}-{v}'
    if (OUT/'runs'/name/'cleanup.json').exists():continue
    one(name,v)
 else:raise ValueError(phase)
