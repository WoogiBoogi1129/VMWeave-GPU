#!/usr/bin/env python3
"""Offline audit of retained diagnosis, not a CNN functionality PASS."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

def validate(root):
    expected = {'cpu-reference': 0, 'gpu-basic': 0, 'conv-forward': -11,
                'conv-train': -11, 'conv-bn': -11, 'conv-forward-loader': -11,
                'conv-forward-calltrace': -11, 'cudnn-stream-repro': -11,
                'gpu-after-failures': 0}
    protocol = json.loads((root/'protocol.json').read_text())
    base = json.loads((root/'sources/baseline-configmap.json').read_text())
    diag = json.loads((root/'sources/diagnostic-configmap.json').read_text())
    for name, sha in protocol['sourceSHA256'].items():
        assert hashlib.sha256(base['data'][name].encode()).hexdigest() == sha
    rows = []
    for name, code in expected.items():
        d = root/name; pod = json.loads((d/'pod.json').read_text())
        submitted = json.loads((d/'submitted.json').read_text())
        assert submitted['spec']['containers'][0]['image'] == 'docker.io/pytorch/pytorch@sha256:eee11b3b3872a8c838e35ef48f08b2d5def2080902c7f666831310ca1a0ef2be'
        cs = next(c for c in pod['status']['containerStatuses'] if c['name'] == 'pytorch')
        assert cs['imageID'] == submitted['spec']['containers'][0]['image']
        status = json.loads((d/'exit.json').read_text())
        assert status['returncode'] == code and not status['timeout'], (name, status)
        assert cs['state']['terminated']['exitCode'] == (0 if code == 0 else 139)
        events = [json.loads(line) for line in (d/'stdout.txt').read_text().splitlines()]
        identity = next(e for e in events if e['event'] == 'identity')
        cm = next(v['configMap']['name'] for v in pod['spec']['volumes'] if v['name'] == 'code')
        source = (base if cm == 'cnn-code' else diag)['data']['probe.py']
        assert identity['sourceSHA256'] == hashlib.sha256(source.encode()).hexdigest()
        assert any(e['event'] == 'PASS' for e in events) == (code == 0)
        if name != 'cpu-reference': assert any(e['event'] == 'cuda-basic-pass' for e in events)
        if code != 0:
            assert not any(e['event'] == 'comparison-pass' for e in events)
            assert not any(e['event'] == 'forward-complete' and e['stage'].startswith('cuda-') for e in events)
        rows.append(dict(name=name, phase=pod['status']['phase'], returncode=code,
                         lastStage=events[-1]['stage'], cpuReferences=[e.get('fixture') for e in events if e['event']=='cpu-reference-pass'],
                         cnnGPUComparison='NOT_REACHED' if code else 'NOT_APPLICABLE', cudnnReported=identity['cudnn']))
    trace = (root/'conv-forward-calltrace/stderr.txt').read_text()
    assert 'CNN_API_ENTER cudnnSetStream' in trace and 'getCudnnHandle' in trace
    assert 'CNN_API_RETURN cudnnSetStream' not in trace
    direct = [json.loads(s) for s in (root/'cudnn-stream-repro/stdout.txt').read_text().splitlines()]
    assert any(e.get('api') == 'cudnnCreate' and e.get('status') == 0 for e in direct)
    assert direct[-1]['stage'] == 'direct-cudnn-setstream'
    for case in ['conv-forward','conv-train','conv-bn']:
        assert (root/'cpu-reference'/(case+'-cpu.pt')).stat().st_size > 0
    shutdown = json.loads((root/'shutdown.json').read_text())
    assert shutdown['finalVM']['spec']['runStrategy'] == 'Halted'
    assert shutdown['finalChannel']['status']['phase'] == 'Stopped'
    assert not shutdown['events'][-1]['vmiPresent']
    restore = json.loads((root/'restoration.json').read_text())
    assert all(item['uidUnchanged'] and item['configuredSpecUnchanged'] for item in restore.values())
    assert restore['sharedmemorychannel']['exactSpecUnchanged'] and restore['gpurequest']['exactSpecUnchanged']
    changes = json.loads((root/'vm-session-identity-changes.json').read_text())
    assert {c['path'] for c in changes} == {
        '/template/metadata/annotations/vmweave.io/shm-allocation',
        '/template/metadata/annotations/vmweave.io/shm-generation',
        '/template/spec/volumes/1/cloudInitNoCloud/userData'}
    def normalized(spec):
        value = copy.deepcopy(spec)
        for key in ['vmweave.io/shm-allocation', 'vmweave.io/shm-generation']:
            value['template']['metadata']['annotations'].pop(key, None)
        for vol in value['template']['spec']['volumes']:
            if 'cloudInitNoCloud' in vol:
                cloud = vol['cloudInitNoCloud']
                cloud['userData'] = ''.join(line for line in cloud['userData'].splitlines(keepends=True)
                                            if not line.startswith('# vmweave-layout-b64: '))
        return value
    for kind in ['vm','sharedmemorychannel','gpurequest']:
        before = json.loads((root/f'before-{kind}.json').read_text())
        after = json.loads((root/f'after-{kind}.json').read_text())
        assert before['metadata']['uid'] == after['metadata']['uid']
        if kind == 'vm': assert normalized(before['spec']) == normalized(after['spec'])
        else: assert before['spec'] == after['spec']
    return dict(evidenceAudit='PASS', cnnTrainingSupported=False, podCount=9,
                successfulPods=3, failedDiagnosticPods=6, results=rows,
                firstLocalizedFailure='native cudnnSetStream called with remote cuDNN handle',
                versionObservation={'guestNative':91900,'workerReported':90800},
                cleanup='Halted / Channel Stopped / original UID and configuration preserved; automatic session identity changed')

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--root', type=Path, default=Path(__file__).parent/'results/20261107')
    p.add_argument('--write-summary', action='store_true'); a = p.parse_args()
    result = validate(a.root)
    if a.write_summary: (a.root/'summary.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
