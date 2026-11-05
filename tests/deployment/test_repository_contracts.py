"""Guard release drift, corrupted fixtures, and missed image build inputs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import shutil
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RepositoryContracts(unittest.TestCase):
    def test_published_tag_and_chart_can_have_different_versions(self):
        module = load('check-doc-contracts')
        current = json.loads((ROOT / 'deploy/releases/current.json').read_text())
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ('charts/vmweave-operator/Chart.yaml', 'versions.lock.yaml',
                         'deploy/releases/current.json', current['record'],
                         'docs/releases/index.md', current['guide']):
                dest = root / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, dest)
            record = root / current['record']
            data = json.loads(record.read_text())
            data['chart']['version'] = '0.0.0-independent-chart'
            record.write_text(json.dumps(data))
            module.check_release_contract(root)
            data['tag'] = 'v0.0.0-wrong-record'
            record.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'Current release pointer'):
                module.check_release_contract(root)

    def test_release_contract_and_reject_stale_lock(self):
        module = load('check-doc-contracts')
        module.check_release_contract(ROOT)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ('charts/vmweave-operator/Chart.yaml', 'versions.lock.yaml'):
                dest = root / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, dest)
            lock = yaml.safe_load((root / 'versions.lock.yaml').read_text())
            lock['deployment']['chartVersion'] = '0.0.0-stale'
            (root / 'versions.lock.yaml').write_text(yaml.safe_dump(lock))
            with self.assertRaisesRegex(ValueError, 'Chart version'):
                module.check_release_contract(root)

    def test_snapshot_rejects_byte_changes(self):
        module = load('check-repository')
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            content = b'observed\r\n'
            (root / 'observation.txt').write_bytes(content)
            manifest = {'sourceRevision': 'a' * 40, 'files': [
                {'path': 'observation.txt', 'sourcePath': 'original.txt',
                 'sha256': hashlib.sha256(content).hexdigest()}]}
            (root / 'manifest.json').write_text(json.dumps(manifest))
            module.check_snapshot(root, 'manifest.json')
            (root / 'observation.txt').write_bytes(b'observed\n')
            with self.assertRaisesRegex(ValueError, 'Snapshot hash mismatch'):
                module.check_snapshot(root, 'manifest.json')

    def test_image_filters_cover_local_copy_inputs(self):
        workflow = yaml.load((ROOT / '.github/workflows/images.yml').read_text(), Loader=yaml.BaseLoader)
        matrix = workflow['jobs']['build']['strategy']['matrix']['include']
        inputs = set()
        for entry in matrix:
            dockerfile = ROOT / 'images/vmweave' / entry['file']
            for line in dockerfile.read_text().replace('\\\n', ' ').splitlines():
                if not line.lstrip().startswith('COPY '):
                    continue
                args = shlex.split(line)
                if not args or args[0] != 'COPY' or args[1].startswith('--from='):
                    continue
                for source in args[1:-1]:
                    path = ROOT / source
                    self.assertTrue(path.exists(), source)
                    files = path.rglob('*') if path.is_dir() else [path]
                    inputs.update(p.relative_to(ROOT).as_posix() for p in files
                                  if p.is_file() and '__pycache__' not in p.parts
                                  and not p.name.endswith('.pyc'))
        self.assertTrue(inputs)
        for event in ('pull_request', 'push'):
            patterns = workflow['on'][event]['paths']
            for source in inputs:
                expressions = [re.escape(pattern).replace(r'\*\*', '.*').replace(r'\*', '[^/]*')
                               for pattern in patterns]
                self.assertTrue(any(re.fullmatch(expression, source) for expression in expressions),
                                f'{event} does not cover build input: {source}')


if __name__ == '__main__':
    unittest.main()
