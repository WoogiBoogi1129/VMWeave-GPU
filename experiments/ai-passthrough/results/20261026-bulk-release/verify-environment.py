import json,subprocess,shlex
from pathlib import Path
b=Path(__file__).resolve().parent
v=json.loads(subprocess.check_output(['kubectl','get','vmi','vmweave-k8s-01','-n','vmweave-test-a','-o','json'],text=True));ip=v['status']['interfaces'][0]['ipAddress']
ssh=['ssh','-i','.local/system-comparison-20261001/artifacts/guest-key','-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','ubuntu@'+ip]
def run(cmd):return subprocess.check_output(ssh+[cmd],text=True,timeout=15).strip()
code="from pathlib import Path; import subprocess; p=subprocess.check_output(['systemctl','show','vmweave-guest-broker.service','-p','MainPID','--value'],text=True).strip(); e=dict(x.split(b'=',1) for x in Path('/proc/'+p+'/environ').read_bytes().split(b'\\0') if b'=' in x); print(e.get(b'VMWEAVE_BULK_COPY',b'').decode())"
result={'broker_bulk':run('sudo python3 -c '+shlex.quote(code)), 'login_bulk':run('bash -lc '+shlex.quote('printf %s "$VMWEAVE_BULK_COPY"')),'service':run('systemctl is-active vmweave-guest-broker.service'),'sourceRevision':run('cat /opt/vmweave/source-revision.txt')}
assert result['broker_bulk']==result['login_bulk']=='1' and result['service']=='active',result
(b/'live-environment.json').write_text(json.dumps(result,indent=2));print(result)
