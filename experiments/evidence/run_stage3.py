"""Three independent VM pairs: different memory limits, expected OOM, continued work.
Raw stdout/stderr, host receipt timestamps, UID-scoped cleanup. No result UI/video.
"""
import argparse,csv,gzip,hashlib,json,shutil,subprocess,threading,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from campaign_runtime import Run,ROOT,NS,GPU,call,k,get,save,wait
from run_stage1 import clean_object
from run_stage2_logs import WORKER

class Probe:
 def __init__(self,run,role,out,seed):
  self.run=run;self.role=role;self.out=out;self.rows=[];self.receipts=[];self.failure=None
  out.mkdir(parents=True,exist_ok=False)
  self.command='cd /tmp/campaign && sudo env FLYT_TRACE_REQUESTS=1 FLYT_LAYOUT=/tmp/campaign/layout.bin FLYT_IVSHMEM_BDF='+run.bdf+' FLYT_SLOT=0 LD_LIBRARY_PATH=/tmp/campaign ./stage3-probe '+role+' '+str(seed)
  save(out/'command.json',{'guest_command':self.command,'worker_log_command':['kubectl','logs','-n',NS,run.worker]})
  self.err=(out/'guest-stderr.txt').open('w');self.proc=subprocess.Popen(run.ssh+[self.command],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.err,text=True,bufsize=1)
  self.thread=threading.Thread(target=self.read);self.thread.start()
 def read(self):
  try:
   with (self.out/'stdout.jsonl').open('w') as f,(self.out/'host-receipts.jsonl').open('w') as g:
    for line in self.proc.stdout:
     stamp=time.time();f.write(line);f.flush();row=json.loads(line);receipt={'host_received_utc':stamp,'record':row};g.write(json.dumps(receipt)+'\n');g.flush();self.receipts.append(receipt);self.rows.append(row)
  except Exception as e:self.failure=str(e)
 def await_event(self,event,phase=None):
  def check():
   if self.failure:raise RuntimeError(self.failure)
   matches=[r for r in self.rows if r['event']==event and (phase is None or r.get('phase')==phase)]
   if matches:return matches[-1]
   if self.proc.poll() is not None:raise RuntimeError('Probe exited: '+self.role+' '+str(self.proc.returncode))
  return wait(check,seconds=45)
 def send(self,command):
  stamp=time.time();self.proc.stdin.write(command+'\n');self.proc.stdin.flush()
  with (self.out/'stdin-commands.jsonl').open('a') as f:f.write(json.dumps({'host_sent_utc':stamp,'command':command})+'\n')
  return stamp
 def finish(self):
  code=self.proc.wait(timeout=45);self.thread.join(5);self.err.close();save(self.out/'process.json',{'exit_code':code})
  if code or self.failure:raise RuntimeError('Probe failed '+self.role)

def snapshot(run,out):
 c=get('flytsharedmemorychannel',run.name+'-channel')
 save(out/'applied.json',{key:clean_object(get(kind,name),pod=key=='worker') for key,kind,name in [('request','flytgpurequest',run.name+'-request'),('profile','flytgpuprofile',run.name+'-profile'),('channel','flytsharedmemorychannel',run.name+'-channel'),('worker','pod',run.worker)]})
 save(out/'runtime-libraries.json',json.loads(k(['exec','-i','-n',NS,'evidence-c28-affinity','--','python3','-',c['status']['workerPodUID']],input=(ROOT/'experiments/evidence/campaign_runtime_info.py').read_text())))
 save(out/'trace-binding.json',{'allocation':c['status']['allocation'],'generation':c['status']['generation'],'session_id':c['status']['sessions'][0],'gpu_uuid':c['status']['gpuUUID']})

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();base=a.base.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 baseline=lambda:sorted([{k:x['metadata'][k] for k in ['namespace','name','uid']} for x in json.loads(k(['get','vmi','-A','-o','json']))['items']],key=lambda x:x['uid'])
 before=baseline();save(out/'baseline-vmis.json',before)
 save(out/'protocol.json',{'base_commit':call(['git','rev-parse','HEAD']).strip(),'worker_image':WORKER,'gpu_uuid':GPU,'pairs':3,'quota_mib':{'A':1024,'B':4096},'compute':50,'sessions_per_vm':1,'shm_mib':64,'large_mib':1536,'small_mib':128,'hold_seconds':10,'sample_mib_per_end':1,'kernel_blocks':1024,'kernel_threads':256,'recording':False,'binary_sha256':{n:hashlib.sha256((base/'artifacts'/n).read_bytes()).hexdigest() for n in ['stage3-probe','libflyt_guest.so']}})
 for number in range(1,4):
  pair='pair-'+str(number);po=out/pair;po.mkdir();runs={};probes={};events=[];start=time.time()
  def phase(name,**fields):
   r={'pair':pair,'phase':name,'host_utc':time.time(),**fields};events.append(r);save(po/'phases.json',events);print(json.dumps(r),flush=True)
  try:
   for role in ['A','B']:
    name='evidence-s3-0929-'+str(number)+'-'+role.lower()
    if get('vm',name):raise RuntimeError('VM name exists')
    runs[role]=Run(base,name,compute=50,slot=role.lower(),worker_image=WORKER,memory_mib=1024 if role=='A' else 4096,scope='Stage3 pair '+pair)
   # Independent VMs use separate PVCs and CPU sets.
   with ThreadPoolExecutor(max_workers=2) as pool:
    futures=[pool.submit(r.prepare) for r in runs.values()]
    for f in futures:f.result()
   phase('PREPARED')
   for role,run in runs.items():
    call(['scp','-i',base/'artifacts/guest-key','-o','BatchMode=yes','-o','UserKnownHostsFile='+str(run.out/'known-hosts'),base/'artifacts/stage3-probe','ubuntu@'+run.ip+':/tmp/campaign/'])
    probes[role]=Probe(run,role,po/role,3100+number*10+(role=='B'))
   for role,probe in probes.items():
    probe.await_event('READY');snapshot(runs[role],po/role)
    free=next(r['free_bytes'] for r in probe.rows if r['event']=='MEMINFO' and r['phase']=='ready')
    if free<(1536 if role=='B' else 128)*1048576:raise RuntimeError('Insufficient expected headroom')
   phase('BOTH_READY');time.sleep(10)
   probes['B'].send('large');e=probes['B'].await_event('ALLOC','large');assert e['api_result']==0
   probes['B'].await_event('MEMINFO','after_large');phase('B_LARGE_ALLOCATED');time.sleep(10)
   (po/'gpu-processes.csv').write_text(call(['nvidia-smi','-i',GPU,'--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory','--format=csv']))
   probes['A'].send('large');e=probes['A'].await_event('ALLOC','large');assert e['api_result']==2 and e['live_allocated_bytes']==0
   phase('A_EXPECTED_OOM');time.sleep(10)
   probes['A'].send('small');e=probes['A'].await_event('ALLOC','small');assert e['api_result']==0
   probes['A'].await_event('MEMINFO','after_small');phase('A_SMALL_ALLOCATED');time.sleep(10)
   probes['A'].send('free');probes['A'].await_event('FREE','final');phase('A_FREED');time.sleep(10)
   probes['B'].send('free');probes['B'].await_event('FREE','final');phase('B_FREED');time.sleep(10)
   for probe in probes.values():probe.send('exit')
   for probe in probes.values():probe.finish();assert probe.await_event('RESULT')['status']=='PASS'
   for role,run in runs.items():
    for part in ['head','tail']:
     dest=run.out/('stage3-output-'+part+'.bin')
     call(['scp','-i',base/'artifacts/guest-key','-o','BatchMode=yes','-o','UserKnownHostsFile='+str(run.out/'known-hosts'),'ubuntu@'+run.ip+':/tmp/campaign/'+dest.name,dest])
     (po/role/(dest.name+'.gz')).write_bytes(gzip.compress(dest.read_bytes(),mtime=0))
   phase('BOTH_COMPLETE')
  except Exception as e:
   save(po/'failure.json',{'error':str(e),'host_utc':time.time()});raise
  finally:
   for role,probe in probes.items():
    if probe.proc.poll() is None:
     probe.proc.terminate()
     try:probe.proc.wait(timeout=10)
     except subprocess.TimeoutExpired:probe.proc.kill()
    probe.thread.join(5)
    if not probe.err.closed:probe.err.close()
    if get('pod',runs[role].name+'-channel-worker'):
     (po/role/'worker-stderr.txt').write_text(k(['logs','-n',NS,runs[role].name+'-channel-worker']))
   for role,run in runs.items():
    if not run.uid:
     ch=get('flytsharedmemorychannel',run.name+'-channel')
     if ch and (run.out/'private-prepare'/('FlytSharedMemoryChannel-'+run.name+'-channel.json')).exists():run.uid=ch['metadata']['uid']
    run.close();ro=po/role;ro.mkdir(exist_ok=True)
    if run.uid:
     wait(lambda:not get('vmi',run.name) and not get('pod',run.name+'-channel-worker'),seconds=180)
     for name in ['identity.json','manifest.json','clock-map.json','cpu-pinning.txt','cleanup.json','host-events.jsonl']:
      if (run.out/name).exists():shutil.copy2(run.out/name,ro/name)
     save(ro/'released-channel.json',clean_object(get('flytsharedmemorychannel',run.name+'-channel')))
   phase('RELEASED')
   save(po/'window.json',{'start':start,'end':time.time()})
  from verify_stage3 import verify_pair
  save(po/'validation.json',verify_pair(po));print(pair+' PASS',flush=True)
 after=baseline();assert before==after
 save(out/'final-audit.json',{'baseline_preserved':True,'baseline_vmis':after,'gpu_processes_after':call(['nvidia-smi','-i',GPU,'--query-compute-apps=gpu_uuid,pid','--format=csv,noheader']).strip()})
 print('ALL THREE PAIRS PASS',flush=True)
if __name__=='__main__':main()
