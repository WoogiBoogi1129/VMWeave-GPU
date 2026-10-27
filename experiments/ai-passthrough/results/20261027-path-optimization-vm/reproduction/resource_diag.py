"""Coarse process/container accounting outside the formal performance campaign."""
import json,shlex,time

def snapshot(h,s):
    assert s['name'].startswith('path-w-1027-qual-spin')
    worker_script="import json;from pathlib import Path;p=Path('/sys/fs/cgroup');print(json.dumps({f:(p/f).read_text() for f in ['cpu.stat','memory.current','memory.peak']}))"
    worker=json.loads(h.k('exec',s['worker'],'-n',s['namespace'],'--','python3','-c',worker_script))
    broker_script="""import os,json,subprocess
from pathlib import Path
pid=subprocess.check_output(['systemctl','show','vmweave-guest-broker.service','-p','MainPID','--value'],text=True).strip()
p=Path('/proc')/pid
s=(p/'stat').read_text().rsplit(')',1)[1].split()
status=(p/'status').read_text()
print(json.dumps({'pid':int(pid),'cpu_ticks':int(s[11])+int(s[12]),'clock_ticks':os.sysconf('SC_CLK_TCK'),'status':status}))
"""
    broker=json.loads(h.remote(s,'sudo python3 -c '+shlex.quote(broker_script)))
    return {'wall_unix':time.time(),'worker_container':worker,'guest_broker':broker}

def summarize(before,after):
    def usage(d):return int(dict(x.split() for x in d['worker_container']['cpu.stat'].splitlines())['usage_usec'])/1e6
    assert before['guest_broker']['pid']==after['guest_broker']['pid']
    return {'measurement_scope':'whole microbenchmark process including setup and correctness copies; not per API; worker includes HAMi background threads',
            'wall_seconds':after['wall_unix']-before['wall_unix'],
            'worker_container_cpu_seconds':usage(after)-usage(before),
            'guest_broker_cpu_seconds':(after['guest_broker']['cpu_ticks']-before['guest_broker']['cpu_ticks'])/after['guest_broker']['clock_ticks'],
            'worker_memory_current_bytes':int(after['worker_container']['memory.current']),
            'worker_memory_peak_bytes':int(after['worker_container']['memory.peak'])}
