"""Host-PID helper sampler. Only numeric CPU counters/affinity/cgroup are emitted."""
import json,os,time
from pathlib import Path
os.sched_setaffinity(0,{48,49,50,51})
while True:
 started=time.time();rows=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   command=(p/'cmdline').read_bytes().split(b'\0')[0].decode(errors='replace')
   if not any(command.endswith(x) for x in ('qemu-kvm','flyt-shm-worker','campaign-probe-native')):continue
   raw=(p/'stat').read_text();values=raw[raw.rfind(')')+2:].split()
   rows.append({'pid':int(p.name),'program':command.rsplit('/',1)[-1],'cgroup':(p/'cgroup').read_text().strip(),
    'user_ticks':int(values[11]),'system_ticks':int(values[12]),'start_ticks':int(values[19]),'cpus':sorted(os.sched_getaffinity(int(p.name)))})
  except (FileNotFoundError,ProcessLookupError):continue
 print(json.dumps({'utc_seconds':started,'clock_ticks':os.sysconf('SC_CLK_TCK'),'processes':rows}),flush=True)
 time.sleep(max(.1,1-(time.time()-started)))
