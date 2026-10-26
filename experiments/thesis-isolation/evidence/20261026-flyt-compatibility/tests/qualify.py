import json,subprocess,threading,queue,time,sys
from pathlib import Path
R=Path.cwd();B=R/'.local/flyt-compatibility-20261026';O=R/'experiments/thesis-isolation/results/20261026-flyt-compatibility';out=O/('qualification-'+str(time.time_ns()));out.mkdir()
class Probe:
 def __init__(self,side):
  self.side=side;self.q=queue.Queue();self.f=(out/(side+'-process.log')).open('w');cfg=json.loads((B/side/'ssh.json').read_text())
  self.p=subprocess.Popen(cfg['ssh']+['sudo timeout -k 5 600 env -u LD_PRELOAD LD_LIBRARY_PATH=/tmp/flyt-test:/opt/flyt-cuda-libs /opt/torch-venv/bin/python3 -u /tmp/flyt-test/qualification.py'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
  threading.Thread(target=self.read,daemon=True).start()
 def read(self):
  for line in self.p.stdout:
   self.f.write(line);self.f.flush()
   try:
    row=json.loads(line)
    if isinstance(row,dict) and 'event' in row:self.q.put(row)
   except ValueError:pass
  self.q.put({'event':'EOF','returncode':self.p.wait()})
 def send(self,line):self.p.stdin.write(line+'\n');self.p.stdin.flush()
 def until(self,event,seconds=90):
  end=time.monotonic()+seconds;rows=[]
  while True:
   r=self.q.get(timeout=max(.1,end-time.monotonic()));rows.append(r)
   if r['event']=='EOF':raise RuntimeError(self.side+' process ended: '+str(r))
   if r['event']==event:return rows
 def close(self):
  if self.p.poll() is None:
   try:self.send('quit');self.p.wait(timeout=15)
   except Exception:self.p.terminate()
  self.f.close()
code=(R/'experiments/thesis-isolation/probes/flyt_mps_mlp.py').read_text()
code=code.replace(" if parts[0]=='load':", """ if parts[0]=='quota':
  try:
   boundary=torch.empty(2*1024*1024*1024,device='cuda',dtype=torch.uint8)
   print(json.dumps({'event':'quota','rejected':False}),flush=True);del boundary
  except torch.OutOfMemoryError as e:
   print(json.dumps({'event':'quota','rejected':True,'error':str(e)}),flush=True)
  continue
 if parts[0]=='load':""")
(out/'qualification.py').write_text(code)
for side in ['a','b']:
 cfg=json.loads((B/side/'ssh.json').read_text())
 subprocess.run(cfg['ssh']+['cat > /tmp/flyt-test/qualification.py'],input=code,text=True,check=True)
ps=[];status={'pass':False,'diagnostic_only':True,'performance_samples':0,'stages':[]}
def save(name,rows): (out/(name+'.json')).write_text(json.dumps(rows,indent=2))
def checked(rows):
 req=[r for r in rows if r['event']=='request'];assert req and all(r['code']==0 for r in req),req[-1:] ;return len(req)
try:
 ps=[Probe(s) for s in ['a','b']]
 for p in ps:save(p.side+'-ready',p.until('ready',300))
 print('BOTH_READY',flush=True)
 for p in ps:p.send('observe 2')
 for p in ps:
  rows=p.until('done');save(p.side+'-concurrent',rows);checked(rows)
 status['stages'].append('two_vm_correctness');print('TWO_VM_PASS',flush=True)
 for campaign in ['original','expanded']:
  for mode in ['memory','compute']:
   name=campaign+'-'+mode;ps[1].send('load '+mode+' 4 '+campaign);save(name+'-start',ps[1].until('load_started'))
   ps[0].send('observe 2');rows=ps[0].until('done');save(name+'-observer',rows);checked(rows)
   rows=ps[1].until('done');save(name+'-load',rows);assert rows[-1]['completed_kernels']>0
   status['stages'].append(name);print(name,'PASS',flush=True)
 ps[0].send('quota');rows=ps[0].until('quota');save('quota',rows);assert rows[-1]['rejected']
 status['stages'].append('quota_rejection');status['pass']=True
except Exception as e:status['error']=repr(e);print('FAIL',repr(e),flush=True)
finally:
 for p in ps:p.close()
 for side in ['a','b']:
  p=subprocess.run(['kubectl','-n','flyt-compat-1026-'+side,'exec','flyt-server','-c','server','--','cat','/tmp/node.log'],capture_output=True);(out/(side+'-server.log')).write_bytes(p.stdout+p.stderr)
 save('status',status);print(out, json.dumps(status),flush=True)
