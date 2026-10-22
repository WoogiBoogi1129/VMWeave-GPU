"""Kill exactly one canary session child, scoped by an externally verified Pod UID."""
import json,os,re,signal,sys
from pathlib import Path
uid=sys.argv[1];assert re.fullmatch('[a-f0-9-]{36}',uid)
found=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  cg=(p/'cgroup').read_text();args=(p/'cmdline').read_bytes().split(b'\0')
  if uid not in cg and uid.replace('-','_') not in cg:continue
  if len(args)<3 or args[0]!=b'vmweave-shm-session-worker' or args[1]!=b'--session':continue
  found.append(int(p.name))
 except (FileNotFoundError,ProcessLookupError):pass
assert len(found)==1,found
pid=found[0];fd=os.pidfd_open(pid)
# Revalidate cgroup after obtaining a stable process reference.
cg=Path(f'/proc/{pid}/cgroup').read_text();assert uid in cg or uid.replace('-','_') in cg
signal.pidfd_send_signal(fd,signal.SIGKILL);os.close(fd)
print(json.dumps({'pod_uid':uid,'killed_session_pid':pid}))
