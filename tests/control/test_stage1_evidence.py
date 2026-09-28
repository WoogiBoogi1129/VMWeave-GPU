"""Reject misleading Stage 1 claims by perturbing an actual saved observation."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'experiments/evidence'))
from run_stage1 import validate


class Stage1Evidence(unittest.TestCase):
    def setUp(self):
        directory = ROOT/'experiments/evidence/results/2026-09-28-stage1/runs/evidence-s1r-0928-01'
        self.parts = [json.loads((directory/name).read_text()) for name in
                      ['applied.json', 'host-mapping.json', 'runtime-libraries.json', 'guest-bar.json']]

    def test_actual_observation_passes(self):
        self.assertTrue(all(validate(*self.parts).values()))

    def test_applied_quota_mismatch_is_not_request_success(self):
        self.parts[0]['worker']['spec']['containers'][0]['resources']['limits']['nvidia.com/gpumem'] = '1024'
        self.assertFalse(validate(*self.parts)['worker_requests_limits'])

    def test_unrelated_gpu_pid_is_not_worker_execution(self):
        for process in self.parts[0]['gpu_processes']:
            process['pid'] = -1
        self.assertFalse(validate(*self.parts)['actual_worker_gpu_process'])

    def test_same_path_with_different_inode_is_not_shared_backing(self):
        for process in self.parts[1]:
            if process['role'] == 'qemu':
                for mapping in process['backing_mappings']:
                    mapping['inode'] = '-1'
        self.assertFalse(validate(*self.parts)['same_shared_backing_inode'])

    def test_bound_is_not_ready(self):
        self.parts[0]['channel']['status']['phase'] = 'Bound'
        self.assertFalse(validate(*self.parts)['ready_mapped'])


if __name__ == '__main__':
    unittest.main()
