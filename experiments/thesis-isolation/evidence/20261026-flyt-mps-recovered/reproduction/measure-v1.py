import json,subprocess,threading,queue,time,sys
from pathlib import Path
B=Path(sys.argv[1]);out=Path(sys.argv[2]);protocol=json.loads((out/'protocol.json').read_text())
class Probe:
 def __init__(self,side):
  self.side=side;self.q=queue.Queue();self.f=(out/(side+'-process.log')).open('w');cfg=json.loads((B/side/'ssh.json').read_text())
  self.p=subprocess.Popen(cfg['ssh']+['sudo timeout -s TERM -k 5 1500 env -u LD_PRELOAD LD_LIBRARY_PATH=/tmp/flyt-test:/opt/flyt-cuda-libs /opt/torch-venv/bin/python3 -u /tmp/flyt-test/mlp.py'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
  self.thread=threading.Thread(target=self.read,daemon=True);self.thread.start()
 def read(self):
  for line in self.p.stdout:
   self.f.write(line);self.f.flush()
   try:
    row=json.loads(line)
    if isinstance(row,dict) and 'event' in row:
     row['host_received_monotonic']=time.monotonic();self.q.put(row)
   except ValueError:pass
  self.q.put({'event':'EOF','returncode':self.p.wait(),'host_received_monotonic':time.monotonic()})
 def until(self,event,seconds):
  end=time.monotonic()+seconds;rows=[]
  while True:
   r=self.q.get(timeout=max(.1,end-time.monotonic()));rows.append(r)
   if r['event']=='EOF':raise RuntimeError(self.side+' process ended: '+str(r))
   if r['event']==event:return rows
 def command(self,line,event,seconds):
  self.p.stdin.write(line+'\n');self.p.stdin.flush();return self.until(event,seconds)
 def close(self):
  if self.p.poll() is None:
   try:self.p.stdin.write('quit\n');self.p.stdin.flush();self.p.wait(timeout=15)
   except Exception:self.p.terminate();self.p.wait(timeout=10)
  self.thread.join(timeout=5)
  if not self.thread.is_alive():self.f.close()
def save(name,data):(out/(name+'.json')).write_text(json.dumps(data,indent=2))
telemetry_stop=threading.Event()
def telemetry():
 gpu='GPU-772181af-05a4-0c24-de59-8487bd37c142'
 with (out/'telemetry.jsonl').open('w') as f:
  while not telemetry_stop.is_set():
   row={'time_utc':time.time(),'host_monotonic':time.monotonic(),'cpu_jiffies':Path('/proc/stat').read_text().splitlines()[0]}
   for key,query in [('gpu','timestamp,utilization.gpu,utilization.memory,memory.used,power.draw,clocks.sm,clocks.mem,temperature.gpu'),('processes','pid,used_gpu_memory')]:
    flag='--query-gpu=' if key=='gpu' else '--query-compute-apps='
    try:
     r=subprocess.run(['nvidia-smi','-i',gpu,flag+query,'--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5);row[key]={'returncode':r.returncode,'csv':r.stdout.strip(),'stderr':r.stderr.strip()}
    except Exception as e:row[key]={'error':repr(e)}
   row['process_cpu']={}
   for line in row.get('processes',{}).get('csv','').splitlines():
    pid=line.split(',')[0].strip()
    if pid.isdigit():
     try:row['process_cpu'][pid]=Path('/proc',pid,'stat').read_text()
     except OSError:pass
   f.write(json.dumps(row)+'\n');f.flush();telemetry_stop.wait(1)
telemetry_thread=threading.Thread(target=telemetry,daemon=True);telemetry_thread.start()
ps={};results=[];stage='initialization';ok=False
try:
 ps={s:Probe(s) for s in ['a','b']}
 for side,p in ps.items():save(side+'-ready',p.until('ready',300))
 observer=ps[protocol['direction'][0]];load=ps[protocol['direction'][1]]
 print('BOTH_READY',flush=True)
 for condition in protocol['order']:
  stage=condition;print('START',condition,flush=True)
  if condition!='baseline':save(condition+'-load-start',load.command('load '+condition+' 130 '+protocol['campaign'],'load_started',180))
  observed=observer.command('observe 120','done',180);save(condition+'-observer',observed)
  req=[r for r in observed if r['event']=='request'];done=observed[-1]
  assert req and len(req)==done['attempts'] and all(r['code']==0 for r in req),'correctness/request failure'
  assert done['elapsed_s']>=120,'short observer interval'
  if condition!='baseline':
   loaded=load.until('done',180);save(condition+'-load',loaded)
   assert loaded[-1]['completed_kernels']>0 and loaded[-1]['elapsed_s']>=130,'short/empty load'
   assert loaded[-1]['host_received_monotonic']>done['host_received_monotonic'],'load ended before observer'
  results.append({'condition':condition,'attempts':len(req),'successful':len(req),'elapsed_s':done['elapsed_s'],'throughput_rps':len(req)/done['elapsed_s'],'max_abs_error':max(r['max_abs_error'] for r in req)})
  save('results',results);print('DONE',condition,json.dumps(results[-1]),flush=True)
 save('complete',{'completed_conditions':3,'performance_samples':3});ok=True
except Exception as e:
 save('failure',{'error':repr(e),'stage':stage,'completed_conditions':len(results)});print('FAILED',repr(e),flush=True)
finally:
 for p in ps.values():p.close()
 telemetry_stop.set();telemetry_thread.join(timeout=12)
sys.exit(0 if ok else 1)
