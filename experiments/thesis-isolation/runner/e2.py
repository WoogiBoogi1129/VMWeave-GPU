import argparse,concurrent.futures,random,math
from campaign import *
from environment import BUNDLE, validate
class MLP(Probe):
 def __init__(self,s):
  self.s=s;self.q=queue.Queue();self.rows=[]
  self.log=(s.out/'requests-events.jsonl').open('w');self.err=(s.out/'probe-stderr.txt').open('w')
  call(s.scp+[str(ROOT/'experiments/thesis-isolation/probes/mlp.py'),'ubuntu@'+s.ip+':/tmp/perf/mlp.py'])
  with BUNDLE.open('rb') as bundle,(s.out/'bootstrap.txt').open('w') as log:
   subprocess.run(s.ssh+['sudo tar -xz -C / opt/torch-venv opt/flyt-cuda-libs'],stdin=bundle,stdout=log,stderr=log,check=True,timeout=300)
  call(s.ssh+['ln -s libflyt_guest.so /tmp/perf/libcuda.so.1'])
  cmd=s.command('unused',[])[-1].split('/tmp/perf/unused')[0]
  cmd=cmd.replace('LD_LIBRARY_PATH=/tmp/perf ','LD_LIBRARY_PATH=/tmp/perf:/opt/flyt-cuda-libs LD_PRELOAD=/tmp/perf/libflyt_guest.so ')
  cmd+=' /opt/torch-venv/bin/python /tmp/perf/mlp.py'
  self.p=subprocess.Popen(s.ssh+[cmd],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.err,text=True,bufsize=1)
  def reader():
   for line in self.p.stdout:
    try:r=json.loads(line)
    except ValueError:r={'event':'unparsed','text':line}
    r['received_host_utc']=time.time();self.rows.append(r);self.log.write(json.dumps(r)+'\n');self.log.flush();self.q.put(r)
   self.q.put({'event':'eof'})
  self.thread=threading.Thread(target=reader,daemon=True);self.thread.start();self.ready=self.until('ready',180)
if __name__=='__main__':
 validate()
 run_id='iso-e2-pilot-'+time.strftime('%Y%m%d%H%M%S',time.gmtime())
 s=Session(run_id,memory=2048);p=None
 try:
  s.prepare();p=MLP(s);freeze(s);rows=p.command('observe 30',70)
  save(s.out/'pilot.json',{'ready':p.ready,'rows':rows})
  print('E2_PILOT',p.ready,rows[-1],flush=True)
 except Exception as e:
  save(s.out/'pilot-failure.json',{'error':str(e)});raise
 finally:
  if p:p.close()
  s.close()
