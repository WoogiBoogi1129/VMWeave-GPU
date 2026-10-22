"""Coordinate the GPU probe's Worker-child fault; never target another Pod."""
import json,time,subprocess
from pathlib import Path
D=Path(__file__).resolve().parent;ROOT=D.parents[3];R=ROOT/'.local/math-cache-20261022/results';identity=R/'audit/runs/ai-math-cache-1022/identity.json'
end=time.monotonic()+1800
while not identity.exists():
 assert time.monotonic()<end;time.sleep(2)
i=json.loads(identity.read_text());assert i['worker'].startswith('ai-math-cache-1022')
ssh=['ssh','-i',str(ROOT/'.local/thesis-isolation-20261012/artifacts/guest-key'),'-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(identity.parent/'known-hosts'),'ubuntu@'+i['vm_ip']]
while subprocess.run(ssh+['test -f /tmp/perf/math-worker-fault-ready'],capture_output=True).returncode:
 assert time.monotonic()<end;time.sleep(2)
r=subprocess.run(['kubectl','get','pod',i['worker'],'-n','vmweave-test-a','-o','json'],capture_output=True,text=True,check=True)
assert json.loads(r.stdout)['metadata']['uid']==i['worker_uid']
r=subprocess.run(['kubectl','exec','-i','-n','vmweave-test-a','vmweave-math-cache-admin-1022','--','chroot','/host','python3','-',i['worker_uid']],input=(D/'kill_session.py').read_text(),capture_output=True,text=True,check=True)
(D/'worker-fault-injection.json').write_text(r.stdout)
subprocess.run(ssh+['sudo touch /tmp/perf/math-worker-fault-done'],check=True)
