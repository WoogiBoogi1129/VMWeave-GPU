"""Check user-visible installation boundaries, including rejected unsafe values."""
import json
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[3]
chart=str(ROOT/'charts/vmweave-device-plugin')
base=['helm','template','test',chart]
values=['--set','image.digest=sha256:'+'a'*64,'--set','librarySHA256='+'b'*64,'--set','brokerGID=998']
r=subprocess.run(base+values,capture_output=True,text=True,check=True)
assert 'vmweave.io/device-plugin: enabled' in r.stdout or 'vmweave.io/device-plugin: "enabled"' in r.stdout
assert 'automountServiceAccountToken: false' in r.stdout
assert 'mountPath: /run/vmweave, readOnly: true' in r.stdout
assert 'kind: ClusterRole' not in r.stdout and 'privileged: true' not in r.stdout
for overrides in [[],values+['--set','brokerGID=0'],values+['--set','image.digest=latest'],values+['--set','librarySHA256=unknown']]:
 assert subprocess.run(base+overrides,capture_output=True).returncode!=0
print('PASS chart required values, opt-in selector, mounts and privilege boundaries')
