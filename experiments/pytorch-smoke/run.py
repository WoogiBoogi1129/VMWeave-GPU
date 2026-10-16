"""Site-specific fresh VM validation using the established allocation harness."""
import sys, json, time, subprocess, threading, queue
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments/thesis-isolation/runner'))
import common, session
from environment import BUNDLE, validate
OUT=ROOT/'experiments/pytorch-smoke/results'/time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
common.OUT=session.OUT=OUT
common.HELPER=session.HELPER='pytorch-smoke-admin-1016'
session.IMAGES['worker']=(ROOT/'.local/persistent-20261014/worker-image.txt').read_text().strip()
common.ensure_admin()
s=session.Session('torch-smoke-'+time.strftime('%m%d%H%M%S',time.gmtime()))
s.profile_name='pytorch-smoke-current-50-2048'
p=None
try:
    env=validate();common.save(OUT/'bundle.json',env)
    s.prepare()
    common.save(s.out/'source.json', {'train_source':Path(__file__).with_name('train.py').read_text()})
    print('VM_AND_SSH_READY',s.name,s.ip,flush=True)
    common.save(s.out/'vmi.json',s.get('vmi',s.name))
    common.save(s.out/'worker.json',s.get('pod',s.worker))
    common.call(s.scp+[str(ROOT/'.local/persistent-20261014/build/libflyt_guest.so'),str(Path(__file__).with_name('train.py')),'ubuntu@'+s.ip+':/tmp/perf/'])
    with BUNDLE.open('rb') as bundle,(s.out/'bootstrap.log').open('w') as log:
        subprocess.run(s.ssh+['sudo tar -xz -C / opt/torch-venv opt/flyt-cuda-libs'],stdin=bundle,stdout=log,stderr=log,check=True,timeout=300)
    common.call(s.ssh+['ln -s libflyt_guest.so /tmp/perf/libcuda.so.1'])
    cmd=s.command('unused',[])[-1].split('/tmp/perf/unused')[0].replace('LD_LIBRARY_PATH=/tmp/perf ','LD_LIBRARY_PATH=/tmp/perf:/opt/flyt-cuda-libs LD_PRELOAD=/tmp/perf/libflyt_guest.so ')
    cmd+=' /opt/torch-venv/bin/python /tmp/perf/train.py'
    log=(s.out/'train.jsonl').open('w');err=(s.out/'stderr.txt').open('w')
    p=subprocess.Popen(s.ssh+[cmd],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,bufsize=1)
    q=queue.Queue()
    def read():
        for line in p.stdout:
            log.write(line);log.flush();q.put(line)
        q.put(None)
    threading.Thread(target=read,daemon=True).start()
    result=None; deadline=time.monotonic()+300
    while time.monotonic()<deadline:
        line=q.get(timeout=max(1,deadline-time.monotonic()))
        if line is None: raise RuntimeError('Training exited before result; see stderr')
        print(line,end='',flush=True)
        if json.loads(line).get('event')=='result':result=json.loads(line);break
    if result is None: raise TimeoutError('Training result')
    common.save(s.out/'channel-live.json',s.get(session.CHAN,s.name))
    (s.out/'gpu-live.txt').write_text(common.call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory','--format=csv']))
    (s.out/'worker-processes.txt').write_text(common.k('exec','-n',s.ns,s.worker,'--','sh','-c','cat /proc/1/status; cat /proc/1/cgroup'))
    p.stdin.write('\n');p.stdin.flush();assert p.wait(timeout=30)==0
    common.save(s.out/'result.json',result)
finally:
    if p and p.poll() is None:p.terminate()
    s.close()
    common.k('delete','pod',common.HELPER,'-n',common.NS,'--wait=true','--timeout=60s')
print('RESULTS',s.out,flush=True)
