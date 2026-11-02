#!/usr/bin/env python3
"""Read-only evidence audit, usable without the private cluster artifacts."""
import argparse
import hashlib
import json
from pathlib import Path


def validate(root):
    read = lambda name: json.loads((root / name).read_text())
    correctness = read('correctness/summary.json')
    assert correctness['complete'] and correctness['all_passed']
    assert len(correctness['checks']) == 25 and all(x['passed'] for x in correctness['checks'])
    source_hash = hashlib.sha256((Path(__file__).parent / 'bench.py').read_bytes()).hexdigest()
    seal = read('protocol-seal.json')
    assert seal['protocol_sha256'] == hashlib.sha256((root/'protocol.json').read_bytes()).hexdigest()
    assert seal['benchmark_sha256'] == source_hash and seal['pilot_runs_checked'] == 54
    counts = {}
    gpu_errors = 0
    for phase, expected in [('pilot', 54), ('formal', 300), ('interrupted', 10)]:
        paths = sorted((root / phase).glob('*/*/*/result.json'))
        assert len(paths) == expected, (phase, len(paths))
        exits = list((root / phase).glob('*/*/*/exit.json'))
        assert len(exits) == expected
        for path in paths:
            x = json.loads(path.read_text())
            assert x['source_sha256'] == source_hash and x['completed'] and x['output_finite']
            exit_info = json.loads(path.with_name('exit.json').read_text())
            assert exit_info['returncode'] == 0
            if phase == 'formal':assert exit_info['start_utc'] >= seal['utc']
            for line in path.with_name('gpu.jsonl').read_text().splitlines():
                g = json.loads(line)
                if g.get('returncode') == 0:
                    assert g['csv'].split(',')[0].strip() == 'GPU-772181af-05a4-0c24-de59-8487bd37c142'
                else:
                    gpu_errors += 1
        counts[phase] = len(paths)
    recovery = read('infrastructure/recovery-decision.json')
    assert recovery['preserved_completed_but_unpaired_runs'] == 10
    assert recovery['rerun_block'] == 'b9' and not recovery['performance_based_exclusions']
    assert recovery['replacement_completed_utc'] > recovery['decision_utc']
    probe = read('infrastructure/b9-passthrough-startup-failure/probe/result.json')
    assert probe['passed'] and len(probe['checks']) == 8 and all(x['passed'] for x in probe['checks'])
    assert len(list((root/'formal/b9').glob('*/*/result.json'))) == 30
    assert not list((root/'formal-recovery').glob('*/*/*/result.json'))
    post_failure = read('infrastructure/post-campaign-passthrough-startup-failure/recovery-decision.json')
    assert post_failure['checks_started_before_failure'] == 0
    assert post_failure['formal_runs_already_completed'] == 300 and post_failure['performance_samples_affected'] == 0
    replay = read('offline-reanalysis.json')
    assert replay['passed'] and replay['formal_runs'] == 300
    for name, result in replay['checks'].items():
        assert result['matches'] and result['sha256'] == hashlib.sha256((root/name).read_bytes()).hexdigest()
    transfer = read('transfer-validation/summary.json')
    assert transfer['passed'] and transfer['checks']==24 and transfer['output_hashes_match_across_systems']
    context = read('host-context/summary.json')
    assert not context['preview']
    cleanup = read('cleanup.json')
    assert cleanup['test_resources_removed'] and cleanup['hami_config_exactly_restored']
    assert cleanup['gpu0_compute_idle'] and cleanup['gpu0_driver'] == 'nvidia'
    assert all(x['uid_unchanged'] and x['spec_unchanged'] for x in cleanup['preserved'])
    assert all(x['pod_spec_restored'] for x in cleanup['monitors'])
    release = read('artifacts.json')['release']
    workers = list((root/'inventory').glob('*-vmweave-worker.json'))
    flyt_pods = [p for p in (root/'inventory').glob('flyt-server-*.json') if p.name != 'flyt-server-spec.json']
    assert workers and flyt_pods
    for path in workers + flyt_pods:
        pod = json.loads(path.read_text())
        annotation = pod['metadata']['annotations']['hami.io/vgpu-devices-allocated']
        assert annotation == 'GPU-772181af-05a4-0c24-de59-8487bd37c142,NVIDIA,8192,100:;'
        image = pod['spec']['containers'][0]['image']
        if path in workers:
            assert image == release['worker']
        else:
            assert image == 'localhost/flyt-threeway-server@sha256:3ab91091aad3fed7000e305d02fa89b4d61bc36c6d653aa05db1358929709f09'
    return {'passed': True, 'runs': counts, 'correctness_checks': 25, 'changing_payload_checks':24, 'recovery_probe_checks':8, 'host_context_available':context['available'],
            'benchmark_sha256': source_hash, 'gpu_monitor_errors': gpu_errors,
            'worker_inventories_checked': len(workers), 'flyt_pod_inventories_checked': len(flyt_pods),
            'scope': 'Evidence consistency and restoration assertions; not independent physical remeasurement.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=Path(__file__).parent / 'results/20261102')
    print(json.dumps(validate(p.parse_args().root), indent=2))
