"""Run only after final queries/screenshots. Stop recorded services, archive TSDB."""
import json,os,signal,time,tarfile
from pathlib import Path
b=Path('.local/overhead-20260929');o=Path('experiments/evidence/results/2026-09-29-overhead/monitoring');record=[]
for p in json.loads((b/'monitor-processes.json').read_text()):
 pid=p['pid'];cmd=Path('/proc')/str(pid)/'cmdline'
 if not cmd.exists():record.append({'name':p['name'],'pid':pid,'already_stopped':True});continue
 actual=[v.decode() for v in cmd.read_bytes().split(b'\0') if v]
 if actual!=p['command']:raise RuntimeError('PID identity mismatch: '+str(pid))
 os.kill(pid,signal.SIGTERM);record.append({'name':p['name'],'pid':pid,'signal':'TERM'})
end=time.monotonic()+45
while any((Path('/proc')/str(p['pid'])/'cmdline').exists() and (Path('/proc')/str(p['pid'])/'cmdline').read_bytes() for p in json.loads((b/'monitor-processes.json').read_text())):
 if time.monotonic()>end:raise RuntimeError('Monitoring processes did not exit')
 time.sleep(.2)
with tarfile.open(o/'prometheus-tsdb.tar.gz','w:gz') as tar:tar.add(b/'monitoring/prom-data',arcname='prom-data')
(o/'service-cleanup.json').write_text(json.dumps({'utc':time.time(),'processes':record,'tsdb_archived_after_prometheus_stopped':True},indent=2)+'\n')
print('Recorded services stopped; actual Prometheus TSDB archived.')
