#!/usr/bin/env python3
"""Validate the recorded consolidation evidence; does not contact the cluster."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def read(name):
    return json.loads((ROOT / name).read_text())


def main():
    for name, digest in read('artifacts.json').items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    before, after = read('before-workloads.json'), read('after-workloads.json')
    assert len(before) == len(after) == 47
    for old, new in zip(before, after):
        for key in ['namespace', 'resource', 'name', 'uid', 'specSHA256',
                    'finalizers', 'ownerReferences', 'phase', 'containers']:
            assert old.get(key) == new.get(key), (old['name'], key)
        for key in ['phase', 'reason', 'allocation', 'generation', 'sessions', 'workerPodUID', 'vmiUID']:
            assert old.get('status', {}).get(key) == new.get('status', {}).get(key), (old['name'], key)
    channels = [x for x in after if x['resource'] == 'sharedmemorychannels']
    assert sum(x['status']['phase'] == 'Ready' for x in channels) == 1
    assert sum(x['status']['phase'] == 'Draining' for x in channels) == 3
    checks = read('admission-checks.json')
    assert len(checks) == 10 and all(x['passed'] for x in checks)
    pods = read('operator-pods.json')
    assert len(pods) == 2
    for pod in pods:
        assert pod['namespace'] == 'vmweave-system'
        assert all(c['ready'] and c['restartCount'] == 0 for c in pod['containerStatuses'])
    scopes = ['vmweave-test-a', 'vmweave-test-b', 'vmweave-nested-k8s']
    assert read('values-redacted.json')['management']['namespaces'] == scopes
    assert read('values-redacted.json')['maintenance']['enabled'] is False
    webhook = read('webhook.json')['webhooks'][0]
    assert webhook['namespaceSelector']['matchExpressions'][0]['values'] == scopes
    assert webhook['clientConfig']['service']['namespace'] == 'vmweave-system'
    assert read('gpu-pod.json')['status']['phase'] == 'Succeeded'
    assert read('gpu-stdout.txt')['status'] == 'PASS'
    assert read('gpu-submitted.json')['spec']['containers'][0]['resources']['limits']['vmweave.io/gpu'] == 1
    metrics = (ROOT / 'controller-metrics.txt').read_text()
    for metric in ['errors', 'panics', 'timeouts']:
        assert f'controller_runtime_reconcile_{metric}_total{{controller="channel"}} 0' in metrics
    print('PASS: hashes, 47 preserved objects, 10 admission checks, single Operator, GPU SGEMM')


if __name__ == '__main__':
    main()
