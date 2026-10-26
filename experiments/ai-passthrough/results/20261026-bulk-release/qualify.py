import harness as h
import subprocess,json,sys,time
from pathlib import Path
h.stage=lambda s:None
s=None
try:
 s=h.prepare_vmw('v054-'+sys.argv[1]);h.save(h.B/'current-session.json',s)
 files=[h.B/'copy_probe.py',h.R/'tests/integration/large_copy_gpu.py']
 subprocess.run(s['scp']+[str(p) for p in files]+['ubuntu@'+s['ip']+':/tmp/'],check=True)
 env='sudo env VMWEAVE_BROKER_SOCKET=/run/vmweave/gpu.sock VMWEAVE_BULK_COPY='
 order=['0','1'] if sys.argv[1]=='r1' else ['1','0']
 for mode in order:
  out=h.remote(s,env+mode+' python3 /tmp/large_copy_gpu.py --library /opt/vmweave/lib/libvmweave_guest.so --out /tmp/large.json',timeout=300)
  (h.B/(sys.argv[1]+'-'+mode+'-large.json')).write_text(h.remote(s,'cat /tmp/large.json'))
  h.remote(s,env+mode+' python3 /tmp/copy_probe.py --out /tmp/copy.json',timeout=300)
  (h.B/(sys.argv[1]+'-'+mode+'-copy.json')).write_text(h.remote(s,'cat /tmp/copy.json'))
 print('QUALIFIED',sys.argv[1],flush=True)
finally:
 if s:h.cleanup_vmw(s)
 h.drop_admin()
