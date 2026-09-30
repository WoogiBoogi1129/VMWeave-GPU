"""Render the maintenance boundary, including schema validation."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

@unittest.skipUnless(shutil.which('helm'), 'Helm is required for chart rendering')
class MaintenanceChart(unittest.TestCase):
    def render(self, enabled=False, replicas=1):
        values = {'maintenance': {'enabled': enabled}, 'controller': {'replicas': replicas},
                  'management': {'namespaces': ['team-a', 'team-b']},
                  'image': {'digest': 'sha256:' + 'a'*64}, 'tls': {'caBundle': 'dGVzdA=='}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'values.json'; path.write_text(json.dumps(values))
            return subprocess.run(['helm', 'template', 'vmweave', str(ROOT/'charts/vmweave-operator'),
                                   '-n', 'vmweave-system', '-f', str(path)], text=True, capture_output=True)

    def test_maintenance_stops_only_controller_and_keeps_admission_scope(self):
        for enabled, count in [(False, 1), (True, 0)]:
            with self.subTest(maintenance=enabled):
                result = self.render(enabled); self.assertEqual(result.returncode, 0, result.stderr)
                deployments = [d for d in result.stdout.split('\n---') if '\nkind: Deployment\n' in d]
                self.assertEqual(len(deployments), 2)
                for item in deployments:
                    desired = count if 'name: vmweave-controller\n' in item else 1
                    self.assertEqual(int(re.search(r'\n  replicas: (\d+)', item)[1]), desired)
                    self.assertIn('--namespaces=team-a,team-b', item)
                self.assertIn('kind: ValidatingWebhookConfiguration', result.stdout)
                self.assertIn('namespace: team-a', result.stdout)
                self.assertIn('namespace: team-b', result.stdout)

    def test_normal_replica_and_flag_schema_are_still_enforced(self):
        self.assertNotEqual(self.render(False, 0).returncode, 0)
        self.assertNotEqual(self.render('yes').returncode, 0)
