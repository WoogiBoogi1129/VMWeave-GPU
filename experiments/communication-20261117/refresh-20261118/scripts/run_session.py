from backends import *
import gzip,shutil,threading

def run(mode,label,order,pilot=False,session=None,keep_vm=False):
 out=O/'results'/label;out.mkdir(exist_ok=False)
 s=None;obs=None
 try:
  if session is None:s=start(mode,label)
  else:
   assert mode=='V' and keep_vm
   s={**session,'label':label,'profile':profiles.ACTIVE}
   idle();profiles.audit(s)
   s['clocks']=[]
   for _ in range(5):
    a=time.time_ns();g=int(remote(s,'date +%s%N').strip());b=time.time_ns();s['clocks'].append({'host_before_ns':a,'guest_ns':g,'host_after_ns':b})
   pod=get('pod',s['server'],s['namespace']);assert pod['metadata']['uid']==s['server_uid'] and pod['status']['phase']=='Running'
   save(O/'evidence'/(label+'-session.json'),{k:v for k,v in s.items() if k not in ['ssh','scp']})
   save(O/'evidence'/(label+'-pod.json'),pod)
  cmd=command(s,order,pilot)
  save(out/'execution.json',{'mode':mode,'label':label,'order':order,'pilot':pilot,'command':cmd[-1] if mode!='N' else cmd,'status':'running'})
  uids={'server':s['server_uid']}
  if mode!='N':uids['qemu']=s['launcher_uid']
  observer=B/(label+'-observer.jsonl');stop=observer.with_suffix('.stop');stop.unlink(missing_ok=True);observer.with_suffix('.interference').unlink(missing_ok=True)
  obcmd=['kubectl','exec','-n',NS,'admin','--','chroot','/host','python3',str(O/'scripts/observe.py'),str(observer),json.dumps(uids),GPU]
  obslog=(B/(label+'-observer.stderr')).open('w');obs=S.Popen(obcmd,stdout=obslog,stderr=obslog)
  result=[];captured=False;collector=None
  def collect():
   try:
    code=(O/'scripts/runtime.py').read_text().replace('uids=json.loads(sys.argv[1])','uids='+repr(uids))
    (out/'runtime-libraries.json').write_text(admin(code))
    (out/'gpu-processes.csv').write_text(call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name,used_memory','--format=csv']))
    if mode!='N':
     (out/'client-path.txt').write_text(remote(s,"sudo sh -c 'for p in $(pgrep -x probe); do cat /proc/$p/maps; done'; ss -tnp; ls -l /dev/nvidia* 2>/dev/null || true"))
     if mode=='V':
      code=(O/'scripts/client_runtime.py').read_text()
      (out/'client-effective.json').write_text(remote(s,'sudo python3 -c '+shlex.quote(code)))
   except Exception as e:(out/'collection-error.txt').write_text(str(e))
  with (out/'stdout.jsonl').open('w') as f,(out/'stderr.txt').open('w') as err:
   proc=S.Popen(cmd,stdout=S.PIPE,stderr=err,text=True)
   timer=threading.Timer(1800,proc.kill);timer.start()
   try:
    for line in proc.stdout:
     f.write(line);f.flush()
     try:x=json.loads(line)
     except ValueError:continue
     if x.get('event')=='WARMUP_START' and not captured:
      collector=threading.Thread(target=collect);collector.start();captured=True
     if x.get('event')=='RESULT':
      if observer.with_suffix('.interference').exists():
       proc.terminate();raise RuntimeError('Foreign GPU1 process detected; interval retained but invalid')
      result.append(x);print(label,x['id'],x['correctness'],x['completed'],round(x['elapsed_ns']/1e9,3),flush=True)
      save(B/'progress.json',{'label':label,'mode':mode,'completed_conditions':len(result),'last_condition':x['id'],'utc':time.time()})
    rc=proc.wait()
   finally:
    timer.cancel()
    if proc.poll() is None:proc.terminate()
   if collector:collector.join(timeout=60)
  time.sleep(1.3);stop.touch();obs.wait(timeout=10);obslog.close();shutil.copy2(observer,out/'observer.jsonl')
  save(out/'completion-before-copy.json',{'returncode':rc,'results':result})
  if rc or not result:raise RuntimeError(label+' CUDA execution failed; see stderr.txt')
  if mode=='N':raw=B/'artifacts'/label
  else:
   raw=B/(label+'-raw');raw.mkdir(exist_ok=True)
   call(s['scp']+['ubuntu@'+s['ip']+':/tmp/comm/'+label+'/*.u64',str(raw)],timeout=180)
  for p in raw.glob('*.u64'):
   with p.open('rb') as f,gzip.open(out/(p.name+'.gz'),'wb',compresslevel=6) as z:shutil.copyfileobj(f,z)
  save(out/'execution.json',{'mode':mode,'label':label,'order':order,'pilot':pilot,'returncode':rc,'results':result,'status':'passed' if rc==0 and len(result)==len(order) else 'failed'})
  if rc or len(result)!=len(order):raise RuntimeError(label+' failed')
  return result
 except Exception as e:
  if s is None:
   for name in ['native-server','flyt-server','lupine-server']:
    try:
     if get('pod',name):(out/(name+'-startup.log')).write_text(k('logs','-n',NS,name));save(out/(name+'-startup-pod.json'),get('pod',name))
    except Exception:pass
  save(out/'failure.json',{'error':str(e),'utc':time.time()});raise
 finally:
  if s:
   if obs:
    (B/(label+'-observer.stop')).touch()
    try:obs.wait(timeout=10)
    except Exception:obs.terminate()
   try:(out/'server.log').write_text(k('logs','-n',s['namespace'],s['server']))
   except Exception:pass
   if mode=='F':
    try:(out/'flyt-client-manager.log').write_text(remote(s,'sudo cat /tmp/comm/flyt-manager.log'))
    except Exception:pass
   if keep_vm:
    wait(lambda:GPU not in call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader']),30)
    save(O/'evidence'/(label+'-released.json'),{'utc':time.time(),'gpu_idle':True,'session_closed':True,'vm_kept_running':True,'reservation_retained_for_paired_comparison':True})
   else:close(s)
  else:
   from cleanup import stop_active
   stop_active()
if __name__=='__main__':
 import sys
 run(sys.argv[1],sys.argv[2],list(range(16)),pilot='--pilot' in sys.argv)
