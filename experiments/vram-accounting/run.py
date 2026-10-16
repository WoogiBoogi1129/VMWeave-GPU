"""Site-specific bounded allocation experiments; only own VM allocations are drained."""
import sys,json,time,subprocess,queue,threading,concurrent.futures,urllib.request,hashlib,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'experiments/thesis-isolation/runner'))
import common,session
B=ROOT/'.local/vram-accounting-20261016';OUT=ROOT/'experiments/vram-accounting/results/20261016';OUT.mkdir(parents=True,exist_ok=True)
common.OUT=session.OUT=OUT;common.HELPER=session.HELPER='vram-admin-1016';session.IMAGES['worker']=(ROOT/'.local/persistent-20261014/worker-image.txt').read_text().strip()
# The shared preparation helper can observe a Pod before its Worker process starts.
def ready_k(*args,**kwargs):
 end=time.monotonic()+120
 while True:
  try:return common.k(*args,**kwargs)
  except RuntimeError as error:
   if 'No QEMU/Worker process matched exact Pod UID' not in str(error) or time.monotonic()>=end:raise
   time.sleep(2)
session.k=ready_k
STATE={};LOCK=threading.Lock()
def save(p,v):common.save(p,v)
def update(name,row):
 with LOCK:
  STATE[name]=row;(B/'state.tmp').write_text(json.dumps(STATE));(B/'state.tmp').replace(B/'state.json')
class Probe:
 def __init__(self,s,trace=False):
  self.s=s;self.q=queue.Queue();self.log=(s.out/'events.jsonl').open('w');self.err=(s.out/'stderr.txt').open('w')
  binary='probe-checked' if trace else 'probe'
  common.call(s.scp+[str(B/binary),str(ROOT/'.local/persistent-20261014/build/libflyt_guest.so'),'ubuntu@'+s.ip+':/tmp/perf/'])
  cmd=s.command(binary,[])
  if trace:cmd[-1]=cmd[-1].replace('FLYT_TRACE_REQUESTS=0','FLYT_TRACE_REQUESTS=1')
  self.p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.err,text=True,bufsize=1)
  def read():
   for line in self.p.stdout:self.q.put(line)
   self.q.put(None)
  threading.Thread(target=read,daemon=True).start();initial=self.receive('initial',30)
  assert initial['rc']==0
  if trace:self.receive('initial-after-checker-control',30)
 def receive(self,label,timeout=120):
  line=self.q.get(timeout=timeout)
  if line is None:raise RuntimeError('Probe ended '+self.s.name)
  r=json.loads(line);r.update(label=label,host_utc=time.time());self.log.write(json.dumps(r)+'\n');self.log.flush();update(self.s.name,r)
  if r['info_rc'] or r['verify_rc']:raise RuntimeError('Probe verification '+str(r))
  return r
 def cmd(self,cmd,label=None,hold=0):
  self.p.stdin.write(cmd+'\n');self.p.stdin.flush();r=self.receive(label or cmd)
  if hold:time.sleep(hold)
  return r
 def close(self):
  if self.p.poll() is None:
   self.cmd('clear');self.cmd('quit');self.p.wait(timeout=30)
  self.log.close();self.err.close()
def prepare(name,q,slot='a',cap=50):
 s=session.Session(name,memory=q,slot=slot,cap=cap);s.profile_name=f'vram-current-{cap}-{q}'
 try:s.prepare()
 except Exception:
  s.close();raise
 save(s.out/'worker.json',s.get('pod',s.worker));save(s.out/'vmi.json',s.get('vmi',s.name));print('PREPARED',name,flush=True);return s

def snapshot(s,label):
 h=urllib.request.urlopen('http://10.97.206.19:31992/metrics',timeout=5).read().decode()
 h='\n'.join(x for x in h.splitlines() if s.worker in x and x.startswith('hami_container_device_memory_bytes'))
 gpu=subprocess.check_output(['nvidia-smi','-i',common.GPU,'--query-compute-apps=pid,used_gpu_memory,process_name','--format=csv,noheader'],text=True)
 row={'label':label,'utc':time.time(),'worker':s.worker,'hami':h,'gpu_processes':gpu}
 with (s.out/'accounting.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')

def boundary(p,label):
 p.cmd('clear');i=p.cmd('info');limit=i['total'];lo=0;hi=limit//4096+1
 # Binary search includes an over-quota candidate; successful allocations are fully filled and warm checked.
 r=p.cmd('alloc '+str(hi*4096),label+'-over');assert r['rc']==2,r
 while hi-lo>1:
  mid=(lo+hi)//2;r=p.cmd('alloc '+str(mid*4096),label+'-search')
  if r['rc']==0:lo=mid;p.cmd('clear')
  elif r['rc']==2:hi=mid
  else:raise RuntimeError(str(r))
 r=p.cmd('alloc '+str(lo*4096),label+'-max',hold=2);assert r['rc']==0
 snapshot(p.s,label+'-max');p.cmd('clear')
 r=p.cmd('alloc '+str(hi*4096),label+'-min-fail',hold=1);assert r['rc']==2
 p.cmd('clear');return {'max_success':lo*4096,'min_failure':hi*4096,'initial_free':i['free'],'quota':limit}

def single(name,q,pilot=False):
 s=None;p=None
 try:
  s=prepare(name,q);p=Probe(s);p.cmd('info','B1-context',hold=3);snapshot(s,'B1-context')
  predicted=q*1048576-550*1048576
  fresh=p.cmd('alloc '+str(predicted),'fresh-predicted-max',hold=2);assert fresh['rc']==0
  p.cmd('clear');assert p.cmd('alloc '+str(predicted+4096),'fresh-predicted-over')['rc']==2
  cold=boundary(p,'cold');assert p.cmd('load','B2-module',hold=3)['rc']==0;snapshot(s,'B2-module')
  warm=boundary(p,'warm');steps=[]
  for n in [1,4095,4096,4097,65535,65536,65537,1048576]:
   r=p.cmd('alloc '+str(n),'rounding',hold=.1);steps.append(r);assert r['rc']==0;p.cmd('clear')
  free=warm['max_success'];chunk=16*1048576;count=free//chunk
  r=p.cmd(f'alloc {chunk} {count}','cumulative-base');assert r['rc']==0
  rem=free-count*chunk
  if rem:assert p.cmd('alloc '+str(rem),'cumulative-tail')['rc']==0
  snapshot(s,'cumulative-max');assert p.cmd('alloc 4096','cumulative-over')['rc']==2
  assert p.cmd('check','after-oom-check')['rc']==0
  assert p.cmd('free 0','partial-free')['rc']==0
  assert p.cmd('alloc '+str(chunk),'refill')['rc']==0
  p.cmd('check','refill-check');p.cmd('clear','B4-clear',hold=3);snapshot(s,'B4-clear')
  # Same payload totals with allocation counts kept well below the 4096 implementation ceiling.
  partitions=[]
  for n,c in [(1048576,1),(4096,256),(4095,256),(4097,256)]:
   r=p.cmd(f'alloc {n} {c}','partition');assert r['rc']==0;partitions.append(r);p.cmd('clear')
  assert p.cmd('alloc 134217728','recovery')['rc']==0;p.cmd('check');p.cmd('clear')
  save(s.out/'summary.json',{'status':'PASS','quota_mib':q,'cold':cold,'warm':warm,'rounding':steps,'partitions':partitions,'full_gpu_verification':'warm allocations and cumulative buffers; cold allocations memset+synchronize only','formal':not pilot,'fresh_predicted_max':predicted})
  print('SINGLE_PASS',name,cold,warm,flush=True)
 finally:
  if p:p.close()
  if s:s.close();update(s.name,{'live_requested':0,'free':0,'total':0})

def pair(name,direction):
 sessions=[];probes=[]
 try:
  with concurrent.futures.ThreadPoolExecutor(2) as pool:
   fut=[pool.submit(prepare,name+'-'+slot,q,slot,25) for slot,q in [('a',1024 if direction=='ab' else 4096),('b',4096 if direction=='ab' else 1024)]]
   errors=[]
   for f in fut:
    try:sessions.append(f.result())
    except Exception as error:errors.append(error)
   if errors:raise errors[0]
  for s in sessions:
   p=Probe(s,trace=True);probes.append(p);assert p.cmd('load')['rc']==0
   for n in [1,4097]:
    assert p.cmd('alloc '+str(n),'trace-rounding')['rc']==0;p.cmd('clear')
  rows=[]
  for order in [(0,1),(1,0)]:
   for i in order:
    p=probes[i];info=p.cmd('info');size=info['free']//4096*4096
    r=p.cmd('alloc '+str(size),'pair-near',hold=2);assert r['rc']==0;rows.append({'order':order,'slot':i,'size':size,'result':r})
   for p in probes:
    assert p.cmd('alloc 4096','pair-over')['rc']==2;assert p.cmd('check','pair-survivor')['rc']==0;snapshot(p.s,'pair-full')
   for p in probes:p.cmd('clear')
  for _ in range(4):
   for p in probes:assert p.cmd('alloc 67108864','alternating')['rc']==0
  for p in probes:p.cmd('check');p.cmd('clear');assert p.cmd('alloc 134217728','pair-recovery')['rc']==0;p.cmd('check')
  save(OUT/'pairs'/name/'summary.json',{'status':'PASS','direction':direction,'rows':rows,'sessions':[s.name for s in sessions]});print('PAIR_PASS',name,flush=True)
 finally:
  for p in probes:p.close()
  for s in sessions:s.close();update(s.name,{'live_requested':0,'free':0,'total':0})
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('mode',choices=['pilot','single','pairs']);a.add_argument('--start',type=int,default=1);a.add_argument('--end',type=int,default=5);args=a.parse_args();common.ensure_admin()
 if args.mode=='pilot':single('vram-pilot-'+time.strftime('%H%M%S',time.gmtime()),1024,True)
 elif args.mode=='single':
  for rep in range(args.start,args.end+1):
   for q in [1024,4096]:single(f'vram-single-r{rep}-{q}',q)
 else:
  for rep in range(args.start,args.end+1):
   for direction in ['ab','ba']:pair(f'vram-pair-v3-r{rep}-{direction}',direction)
