"""Offline verification of Stage 1 artifacts, including process-level settings."""
import argparse
import json
from pathlib import Path
from run_stage1 import validate


def read(path):
    return json.loads(path.read_text())


def verify_run(directory):
    applied = read(directory/'applied.json')
    mapping = read(directory/'host-mapping.json')
    runtime = read(directory/'runtime-libraries.json')
    guest = read(directory/'guest-bar.json')
    checks = validate(applied, mapping, runtime, guest)
    worker_pids = {r['pid'] for r in mapping if r['role'] == 'worker'}
    runtime_workers = [r for r in runtime if r['pid'] in worker_pids]
    checks['worker_process_memory_setting'] = bool(runtime_workers) and all(
        r['environment'].get('CUDA_DEVICE_MEMORY_LIMIT_0') == '4096m' for r in runtime_workers)
    checks['worker_process_compute_setting'] = bool(runtime_workers) and all(
        r['environment'].get('CUDA_DEVICE_SM_LIMIT') == '50' for r in runtime_workers)
    checks['current_mapping_generation'] = all(
        a['status'].get('observedGeneration') == a['metadata']['generation'] for a in applied['attachments'])
    metrics = read(directory/'metrics.json')
    result = metrics['result']
    checks['gpu_probe_correctness'] = metrics['execution'] == 'PASS' and metrics['exit_code'] == 0 and (
        result['status'] == 'PASS' and result['checked_elements'] == 524288 and
        result['mismatches'] == 0 and result['nonfinite'] == 0)
    cleanup = read(directory/'cleanup-audit.json')
    checks['normal_cleanup'] = cleanup['released'] and cleanup['execution_objects_absent'] and not cleanup['gpu_processes_after']
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    summary = read(args.bundle/'summary.json')
    assert len(summary) == 3
    assert len({r['allocation'] for r in summary}) == 3
    assert len({r['generation'] for r in summary}) == 3
    checks = {r['run_id']: verify_run(args.bundle/'runs'/r['run_id']) for r in summary}
    assert all(all(values.values()) for values in checks.values()), checks
    before = read(args.bundle/'existing-vmis-before.json')
    after = read(args.bundle/'existing-vmis-after.json')
    assert sorted(before, key=lambda r:r['uid']) == sorted(after, key=lambda r:r['uid'])
    result = {'status': 'PASS', 'completed_independent_runs': 3,
              'preparation_failures_preserved': len(list((args.bundle/'failures').glob('*/metrics.json'))),
              'checks': checks, 'existing_vmis_preserved': True,
              'scope': 'Request and actual binding/settings; enforcement NOT_EVALUATED; no Stage 2 request trace'}
    if args.write:
        (args.bundle/'verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
