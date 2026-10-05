from runtime import *
import runtime
from tcp_runtime import TCP
variants=json.loads((BASE/'variants.json').read_text())
def one(name,variant,metrics=True,mode='sweep',seconds=60,warmup=10,path='S',size=16777216,worker_cpus=None,map_probe=False,pattern_order=0):
 while (BASE/'hold-next-session').exists():time.sleep(1)
 assert GPU not in call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
 s=TCP(BASE,name) if path=='T' else Session(name)
 save(s.out/'condition.json',{'phase':'diagnostic','variant':variant,'metrics':metrics,'mode':mode,'seconds':seconds,'warmup_min_s':warmup,'path':path,'bytes':size,'worker_cpus':worker_cpus or '16-19','mapping_component':map_probe,'pattern_order':pattern_order})
 print('START',name,flush=True)
 log=None;stream=None
 try:
  if path=='S':
   runtime.IMAGES['worker']=json.loads((BASE/'images.json').read_text())['worker'] if variant=='stock' else variants[variant if metrics else variant+'-off']
  s.prepare()
  if worker_cpus:
   assert path=='S'
   uid=get('pod',s.worker)['metadata']['uid']
   (s.out/'worker-affinity-override.json').write_text(k('exec','-i','-n',NS,HELPER,'--','python3','-',uid,worker_cpus,input=(ROOT/'experiments/evidence/campaign_affinity.py').read_text()))
  if map_probe:
   assert path=='S'
   call(s.scp+[str(BASE/'diagnostic/map-probe'),'ubuntu@'+s.ip+':/tmp/perf/'])
   (s.out/'mapping-component.jsonl').write_text(call(s.ssh+['sudo taskset -c 0 /tmp/perf/map-probe /tmp/perf/layout.bin '+s.bdf],timeout=180))
   (s.out/'guest-topology.txt').write_text(call(s.ssh+['lscpu; cat /sys/bus/pci/devices/'+s.bdf+'/resource']))
  files=[BASE/'diagnostic'/('probe-'+path)]
  if path=='S' and variant!='stock':files.append(BASE/'diagnostic/libflyt_guest.so')
  call(s.scp+list(map(str,files))+['ubuntu@'+s.ip+':/tmp/perf/'])
  names=['probe-'+path,'libflyt_guest.so' if path=='S' else 'cricket-client.so']
  effective=call(s.ssh+['sha256sum '+' '.join('/tmp/perf/'+n for n in names)])
  (s.out/'guest-effective-hashes.txt').write_text(effective)
  for line in effective.splitlines():
   digest,file=line.split(maxsplit=1);artifact_name=Path(file).name
   local=BASE/'diagnostic'/artifact_name if artifact_name.startswith('probe-') or (artifact_name=='libflyt_guest.so' and variant!='stock') else BASE/'artifacts'/artifact_name
   assert digest==hashlib.sha256(local.read_bytes()).hexdigest(),artifact_name
  s.worker_hash=hashlib.sha256((BASE/('artifacts/bin/flyt-shm-worker' if variant=='stock' else 'diagnostic/bin/flyt-shm-worker')).read_bytes()).hexdigest()
  if path=='S':
   # Images differ only in settings; turn off metrics with a separate image when requested.
   stream=(s.out/'worker-stream.txt').open('w');log=subprocess.Popen(['kubectl','logs','-f','-n',NS,s.worker],stdout=stream,stderr=subprocess.STDOUT)
  prefix='/tmp/perf/'+name
  args=[mode,size,seconds,warmup,prefix if mode in ['sweep','patterns','regression'] else prefix+'-'+mode+'-'+str(size),'/tmp/perf/work.cubin' if path=='T' else '/tmp/perf/work.ptx']
  if path=='T':cmd=s.ssh+['sudo env SM_CORE='+str(s.sm)+' LD_LIBRARY_PATH=/tmp/perf /tmp/perf/probe-T '+shlex.join(list(map(str,args)))]
  else:
   cmd=s.command('probe-S',args);cmd[-1]=cmd[-1].replace('sudo env ','sudo env HD_PATTERN_ORDER='+str(pattern_order)+' HD_METRICS='+str(int(metrics))+' HD_VARIANT='+variant+' ')
  cmd[-1]=cmd[-1].replace('sudo env ','sudo env HD_COLLECT_BARRIER='+prefix+'.collected ')
  result=execute_stream(s,cmd,prefix)
  assert len(result)==(5 if mode=='regression' else 4 if mode=='sweep' else 2 if mode=='patterns' else 1)
  if log:
   try:log.wait(timeout=30)
   except subprocess.TimeoutExpired:log.terminate();log.wait()
  if path=='S' and variant!='stock':
   assert 'HD_WORKER_EXIT,0\n' in (s.out/'worker-stream.txt').read_text(),'Missing successful post-CUDA teardown marker'
   ended=get('pod',s.worker)
   for _ in range(10):
    if not ended or ended.get('status',{}).get('phase') in ['Succeeded','Failed']:break
    time.sleep(.5);ended=get('pod',s.worker)
   save(s.out/'worker-final-status.json',ended or {'deleted_after_exit_marker':True})
   assert not ended or ended['status']['phase']=='Succeeded','Worker did not exit normally'
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
