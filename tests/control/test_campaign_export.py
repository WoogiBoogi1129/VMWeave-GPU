import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'experiments/evidence'))
from export_campaign import export
from analyze_campaign import json_lines


class CampaignPublication(unittest.TestCase):
    def test_private_preparation_and_auth_are_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)/'private';out=Path(tmp)/'public'
            d=base/'runs/example';d.mkdir(parents=True)
            (d/'stdout.jsonl').write_text('{"event":"RESULT"}\n')
            (d/'private-prepare').mkdir()
            (d/'private-prepare/cloud-init.yaml').write_text('PRIVATE_SENTINEL')
            (d/'private-channel.json').write_text('PRIVATE_SENTINEL')
            (base/'artifacts').mkdir()
            (base/'artifacts/guest-key').write_text('PRIVATE_SENTINEL')
            (base/'grafana-auth.json').write_text('PRIVATE_SENTINEL')
            for name in ['observations.jsonl','cpu-observations.jsonl']:(base/name).write_text('{}\n')
            for name in ['prometheus.yml','dashboards/campaign.json','provisioning/datasources/prometheus.yaml']:
                file=base/'monitoring'/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('{}\n')
            export(base,out)
            self.assertTrue((out/'runs/example/stdout.jsonl').exists())
            for file in out.rglob('*'):
                if file.is_file():self.assertNotIn(b'PRIVATE_SENTINEL',file.read_bytes())
            self.assertFalse((out/'runs/example/private-prepare').exists())

    def test_public_compressed_samples_are_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'samples').mkdir()
            with gzip.open(root/'samples/observations.jsonl.gz','wt') as f:f.write('{"timestamp":1}\n')
            self.assertEqual(list(json_lines(root/'observations.jsonl')),[{'timestamp':1}])


if __name__=='__main__':unittest.main()
