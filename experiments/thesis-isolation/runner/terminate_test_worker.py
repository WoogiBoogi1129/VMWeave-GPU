"""Run in authorized host helper. Exact Pod UID + executable + slot, pidfd kill."""
import os,json,re,signal,sys,time,select
from pathlib import Path
uid=sys.argv[1];assert re.fullmatch(r'[a-f0-9-]{36}',uid)
rows=[]
for p in Path('/proc').glob('[0-9]*'):
 try:
  cg=(p/'cgroup').read_text();args=(p/'cmdline').read_bytes().split(b'\0');exe=os.readlink(p/'exe')
  if uid not in cg and uid.replace('-','_') not in cg:continue
  if exe!='/opt/flyt/bin/flyt-shm-worker' or len(args)!=4 or args[2]!=b'0':continue
  rows.append({'pid':int(p.name),'exe':exe,'args':[x.decode() for x in args[:-1]],'cgroup':cg,'start_ticks':(p/'stat').read_text().rsplit(')',1)[1].split()[19]})
 except (FileNotFoundError,ProcessLookupError,PermissionError):continue
assert len(rows)==1,rows
r=rows[0];pid=r['pid'];fd=os.pidfd_open(pid);p=Path('/proc')/str(pid)
assert (p/'stat').read_text().rsplit(')',1)[1].split()[19]==r['start_ticks']
assert (p/'cgroup').read_text()==r['cgroup'] and os.readlink(p/'exe')==r['exe']
r.update(pod_uid=uid,signal=9,sent_utc=time.time());signal.pidfd_send_signal(fd,signal.SIGKILL)
poll=select.poll();poll.register(fd,select.POLLIN);r['exit_confirmed']=bool(poll.poll(10000));r['confirmed_utc']=time.time();os.close(fd)
print(json.dumps(r));assert r['exit_confirmed']
