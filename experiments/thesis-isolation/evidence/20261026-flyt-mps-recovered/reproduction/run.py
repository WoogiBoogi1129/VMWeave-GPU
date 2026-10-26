import json,subprocess,sys,time,itertools,random,hashlib,shutil
from pathlib import Path
R=Path.cwd();T=R/'.local/flyt-compatibility-20261026';B=R/'.local/flyt-mps-recovered-20261026';O=R/'experiments/thesis-isolation/results/20261026-flyt-mps-recovered';O.mkdir(parents=True,exist_ok=True)
ns='flyt-mps-r1026-';host='/var/lib/vmweave/flyt-mps-recovered-20261026'
protocol=[]
for ci,campaign in enumerate(['original','expanded']):
 orders=list(itertools.permutations(['baseline','memory','compute']));random.Random(20261026+ci).shuffle(orders)
 for i in range(5):
  direction=('ab' if i%2==0 else 'ba') if ci==0 else ('ba' if i%2==0 else 'ab')
  protocol.append({'campaign':campaign,'repetition':i+1,'direction':direction,'order':orders[i],'seconds':120,'warmup':False,'seed':20261026+ci,'label':f'{campaign}-r{i+1}-{direction}'})
(O/'protocol.json').write_text(json.dumps(protocol,indent=2))
manifest=json.loads((R/'experiments/thesis-isolation/evidence/20261026-flyt-compatibility/manifest.json').read_text())
for label,src in [('guest',T/'source/cpu/cricket-client.so'),('host',T/'source-host/cpu/cricket-rpc-server')]:assert hashlib.sha256(src.read_bytes()).hexdigest()==manifest[label]['binary_sha256']
def run(p,log,*args):
 with log.open('w') as f:subprocess.run([sys.executable,str(p),*map(str,args)],stdout=f,stderr=subprocess.STDOUT,check=True)
def transform(s,base,out,label,side=None):
 if side:
  s=s.replace('.local/flyt-compatibility-20261026/'+side,str((base/side).relative_to(R))).replace('experiments/thesis-isolation/results/20261026-flyt-compatibility/'+side,str((out/side).relative_to(R)))
 else:
  s=s.replace('.local/flyt-compatibility-20261026',str(base.relative_to(R))).replace('experiments/thesis-isolation/results/20261026-flyt-compatibility',str(out.relative_to(R)))
 return s.replace('flyt-compat-1026-',ns).replace('flyt-compat-shm-1026-','flyt-mps-r-shm-1026-').replace('/var/lib/vmweave/flyt-compatibility-20261026',host+'/'+label)
for row in protocol:
 label=row['label'];base=B/label;out=O/label;base.mkdir();out.mkdir();(out/'protocol.json').write_text(json.dumps(row,indent=2));print('PREPARE',label,flush=True)
 started=False
 try:
  for side in ['a','b']:
   (base/side).mkdir();(out/side).mkdir()
   for name in ['prepare.py','server-pod.py','start-stack.py']:
    code=transform((T/side/name).read_text(),base,out,label,side)
    p=base/side/name;p.write_text(code)
   run(base/side/'prepare.py',base/side/'prepare.log');started=True
   run(base/side/'server-pod.py',base/side/'server-pod.log')
  for side in ['a','b']:
   run(base/side/'start-stack.py',base/side/'start-stack.log')
   cfg=json.loads((base/side/'ssh.json').read_text());subprocess.run(cfg['ssh']+['ln -sf cricket-client.so /tmp/flyt-test/libcuda.so.1; ln -sf cricket-client.so /tmp/flyt-test/libcuda.so'],check=True)
  p=base/'stage-python.py';p.write_text(transform((T/'stage-python.py').read_text(),base,out,label));run(p,base/'stage-python.log')
  print('MEASURE',label,flush=True);run(B/'measure.py',base/'measure.log',base,out)
  print('COMPLETE',label,flush=True)
 except Exception as e:
  (out/'campaign-failure.json').write_text(json.dumps({'error':repr(e),'time_utc':time.time()},indent=2));print('STOP',label,repr(e),flush=True);raise
 finally:
  if started:
   for side in ['a','b']:
    for name,path in [('node','/tmp/node.log'),('mps','/tmp/flyt-mps-log/server.log')]:
     p=subprocess.run(['kubectl','-n',ns+side,'exec','flyt-server','-c','server','--','cat',path],capture_output=True);(out/(side+'-'+name+'.log')).write_bytes(p.stdout+p.stderr)
   p=base/'cleanup.py';p.write_text(transform((T/'cleanup.py').read_text(),base,out,label));run(p,base/'cleanup.log')
(O/'complete.json').write_text(json.dumps({'completed_repetitions':10,'completed_conditions':30,'time_utc':time.time()},indent=2));print('ALL_COMPLETE',flush=True)
