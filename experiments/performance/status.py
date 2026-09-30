"""Read-only progress; persisted events alone never establish a live driver."""
import json,os,time
from pathlib import Path
from common import OUT,BASE
runs=list((OUT/'runs').iterdir())
counts={key:sum(p.name.startswith('perf-'+key+'-') and (p/'execution.json').exists() and (p/'cleanup.json').exists() and not (p/'failure.json').exists() for p in runs) for key in ['o','c','d']}
interrupted=[p.name for p in runs if (p/'interruption.json').exists()]
unfinished=[p for p in runs if p.name.startswith('perf-') and not (p/'cleanup.json').exists() and p.name not in interrupted]
drivers=[]
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:
  if proc.stat().st_uid!=os.getuid():continue
  args=[x.decode() for x in (proc/'cmdline').read_bytes().split(b'\0') if x]
  if args and Path(args[0]).name.startswith('python') and any(Path(x).name in ['run.py','resume_campaign.py'] and 'performance/' in x for x in args[1:]):drivers.append(int(proc.name))
 except (OSError,UnicodeDecodeError):pass
latest={}
for p in unfinished:
 f=p/'stdout.jsonl';latest[p.name]={'last_event':f.read_text().splitlines()[-1] if f.exists() and f.stat().st_size else 'preparing fresh resources','log_age_s':round(time.time()-f.stat().st_mtime,1) if f.exists() else None}
failures=[{'run':p.name,**json.loads((p/'failure.json').read_text())} for p in runs if p.name.startswith('perf-') and (p/'failure.json').exists()]
print(json.dumps({'completed':counts,'expected':{'o':15,'c':20,'d':40},'driver_pids':drivers,'driver_running':bool(drivers),'active':latest if drivers else {},'unfinished':latest,'interrupted_runs':interrupted,'failures':failures,'all_stages_complete':(OUT/'campaign-execution-complete.json').exists(),'continuation_error':(BASE/'continuation.txt').read_text()[-1200:] if (BASE/'continuation.txt').exists() else ''},ensure_ascii=False))
