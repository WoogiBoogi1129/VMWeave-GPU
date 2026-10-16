import run,subprocess,json,time,queue,threading,argparse
from environment import BUNDLE
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--start',type=int,default=1);p.add_argument('--end',type=int,default=1);a=p.parse_args();run.common.ensure_admin()
for rep in range(a.start,a.end+1):
 for quota in [1024,4096]:
  s=None;proc=None
  try:
   s=run.prepare(f'vram-mlp-boundary-v2-r{rep}-{quota}',quota)
   with BUNDLE.open('rb') as bundle,(s.out/'bootstrap.log').open('w') as log:
    subprocess.run(s.ssh+['sudo tar -xz -C / opt/torch-venv opt/flyt-cuda-libs'],stdin=bundle,stdout=log,stderr=log,check=True,timeout=300)
   run.common.call(s.scp+[str(run.ROOT/'.local/persistent-20261014/build/libflyt_guest.so'),str(Path(__file__).with_name('torch_accounting.py')),str(Path(__file__).with_name('torch_boundary.py')),'ubuntu@'+s.ip+':/tmp/perf/'])
   run.common.call(s.ssh+['ln -s libflyt_guest.so /tmp/perf/libcuda.so.1'])
   cmd=s.command('unused',[])[-1].split('/tmp/perf/unused')[0].replace('LD_LIBRARY_PATH=/tmp/perf ','LD_LIBRARY_PATH=/tmp/perf:/opt/flyt-cuda-libs LD_PRELOAD=/tmp/perf/libflyt_guest.so ')+' /opt/torch-venv/bin/python /tmp/perf/torch_boundary.py'
   q=queue.Queue();rows=[]
   with (s.out/'stderr.txt').open('w') as err,(s.out/'torch-events.jsonl').open('w') as log:
    proc=subprocess.Popen(s.ssh+[cmd],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,bufsize=1)
    def reader():
     for l in proc.stdout:q.put(l)
     q.put(None)
    threading.Thread(target=reader,daemon=True).start()
    while True:
     l=q.get(timeout=180)
     if l is None:raise RuntimeError('torch ended without completion')
     r=json.loads(l);r['host_utc']=time.time();log.write(json.dumps(r)+'\n');log.flush();rows.append(r)
     if r['stage']=='done':break
     run.update(s.name,{'live_requested':r['allocated']+(r.get('direct_requested',0) if r['stage']!='trained-min-fail' else 0),'free':r['free'],'total':r['total'],'stage':r['stage'],'host_utc':r['host_utc']});time.sleep(3);run.snapshot(s,r['stage']);proc.stdin.write('next\n');proc.stdin.flush()
    assert proc.wait(timeout=30)==0
   run.save(s.out/'summary.json',{'status':'PASS','quota_mib':quota,'stages':rows});print('TORCH_PASS',s.name,flush=True)
  finally:
   if proc and proc.poll() is None:proc.terminate()
   if s:s.close();run.update(s.name,{'live_requested':0,'free':0,'total':0})
