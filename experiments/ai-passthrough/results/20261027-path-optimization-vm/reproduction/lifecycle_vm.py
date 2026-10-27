"""Only called with the experiment-owned VM/Worker recorded by the runner."""
import json,subprocess,time,shlex
from pathlib import Path
def qualify(h,s,baseenv,out):
    assert s['name'].startswith('path-w-1027-qual-recovery-')
    out.mkdir(parents=True,exist_ok=False)
    subprocess.run(s['scp']+[str(h.B/'hold_client.py'),'ubuntu@'+s['ip']+':/tmp/short/'],check=True)
    current=h.get('sharedmemorychannel',s['name']);assert current['metadata']['uid']==s['channelUID']
    before=current['status']['generation']
    holdenv=baseenv+' VMWEAVE_STATE_CACHE=1'
    log=open(out/'client.log','w')
    client=subprocess.Popen(s['ssh']+['sudo '+holdenv+' python3 /tmp/short/hold_client.py'],stdout=log,stderr=subprocess.STDOUT)
    try:
        h.wait(lambda:subprocess.run(s['ssh']+['test -f /tmp/short/hold-ready.json'],capture_output=True).returncode==0,30)
        # A second application must be rejected while the first owns the CUDA session.
        probe="import ctypes as c; x=c.CDLL('/opt/vmweave/lib/libvmweave_guest.so'); n=c.c_int(); r=x.cudaGetDeviceCount(c.byref(n)); print(r); assert r==46"
        busy=h.remote(s,'sudo '+baseenv+' python3 -c '+shlex.quote(probe));(out/'busy.log').write_text(busy)
        # SIGKILL only the dedicated Worker CUDA child, preserving its transport parent.
        kill="""import os,signal,json
from pathlib import Path
children=[]
for p in Path('/proc').glob('[0-9]*'):
 try:a=(p/'cmdline').read_bytes().split(b'\\0')
 except OSError:continue
 if len(a)>2 and a[0]==b'vmweave-shm-session-worker' and a[1] in (b'--session',b'--session-arena',b'--session-events'):children.append(int(p.name))
assert len(children)==1,children
os.kill(children[0],signal.SIGKILL);print(json.dumps({'killed_own_cuda_child':children[0]}))
"""
        proof=h.k('exec','-i',s['worker'],'-n',s['namespace'],'--','python3','-',input=kill);(out/'child-kill.json').write_text(proof)
        assert client.wait(timeout=35)==0
        time.sleep(.2)
        recovered=h.remote(s,'sudo '+baseenv+' /tmp/short/correctness');(out/'recovery-kernel.log').write_text(recovered)
        final=h.get('sharedmemorychannel',s['name']);assert final['status']['generation']==before
        h.save(out/'result.json',{'status':'PASS','busy_rejected':True,'cache_fenced_on_child_death':True,'fresh_cuda_session_recovered':True,'channel_generation_preserved':before})
    finally:
        if client.poll() is None:client.terminate();client.wait(10)
        log.close()
