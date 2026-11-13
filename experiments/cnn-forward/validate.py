#!/usr/bin/env python3
"""Audit retained evidence without claiming GPU execution from host tests."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent/'results/20261113'
def read(path):
    return json.loads((ROOT/path).read_text())

manifest = read('artifacts.json')
for name, digest in manifest['evidenceSHA256'].items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest, name
for name, digest in manifest['sourceSHA256'].items():
    assert hashlib.sha256((ROOT/'sources'/name).read_bytes()).hexdigest()==digest, name

for kind in ('vm','vmi','sharedmemorychannel','gpurequest','pods','channelattachments'):
    before = read(f'environment/before-{kind}.json')['items']
    after = read(f'environment/after-{kind}.json')['items']
    def identities(items):
        return {x['metadata']['uid']: x.get('spec') for x in items}
    assert identities(before)==identities(after), kind
blocked = read('baseline-legacy/preflight.json')
assert blocked==dict(status='BLOCKED',phase='Draining',reason='AwaitingDetachEvidence',podCreated=False)
assert not (ROOT/'baseline-legacy/pod.json').exists()
assert not (ROOT/'baseline-legacy/exit.json').exists()

records = [json.loads(x) for x in (ROOT/'cpu-selfcheck.log').read_text().splitlines() if x.startswith('{')]
assert records[0]['mode']=='cpu' and records[0]['torch']=='2.11.0+flyt.cu128'
assert sum(x['stage']=='cpu_reference' for x in records)==16
assert records[-1]==dict(stage='PASS',configs=16,gpu_comparisons=0,backward_executed=False)
checks = (ROOT/'library-tests-final.log').read_text()
assert checks.count('PASS:')>=4 and 'execution mocked' in checks and 'caller storage preservation' in checks
assert 'ERROR: AddressSanitizer' not in (ROOT/'sanitizers.log').read_text()
assert 'runtime error:' not in (ROOT/'sanitizers.log').read_text()
assert manifest['tests']['library']['exitCode']==0 and manifest['tests']['hostRegression']['exitCode']==0
assert manifest['tests']['sanitizers']['exitCode']==0
print(json.dumps(dict(hostChecks='PASS',cpuSelfcheckConfigs=16,vmGPU='BLOCKED',
                      gpuComparisons=0,cnnTrainingSupported=False,resourceSpecsUnchanged=True),indent=2))
