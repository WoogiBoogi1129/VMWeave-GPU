"""Exercise legacy-controller guardrails without a cluster or registry."""
import json
from pathlib import Path
import runpy
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]

class LegacyUtilities(unittest.TestCase):
    def test_active_controller_blocks_install_and_migration_for_both_names(self):
        for variable in ('FLYT_MODE', 'VMWEAVE_MODE'):
            for utility in ('install', 'migrate'):
                with self.subTest(variable=variable, utility=utility), tempfile.TemporaryDirectory() as td:
                    config = Path(td)/'values.json'
                    config.write_text(json.dumps({'management': {'namespaces': ['tenant']}}))
                    script = ROOT/'scripts/operator'/f'{utility}.py'
                    args = ['--values', str(config)] if utility == 'install' else ['--namespace','tenant','--apply','--output',td]
                    def read(command, **kwargs):
                        self.assertEqual(command[:2], ['kubectl', 'get'])
                        if command[2] == 'deployments':
                            return json.dumps({'items':[{'metadata':{'name':'old-controller'},'spec':{'replicas':1,'template':{'spec':{'containers':[{'env':[{'name':variable,'value':'active'}]}]}}}}]})
                        return json.dumps({'items':[]})
                    with patch.object(sys,'argv',[str(script),*args]), patch('subprocess.check_output',side_effect=read), self.assertRaisesRegex(SystemExit,'legacy.*deployment'):
                        runpy.run_path(str(script),run_name='__main__')

    def test_cpu_image_layer_matches_entrypoint_and_retains_alias(self):
        with tempfile.TemporaryDirectory() as td:
            script = ROOT/'scripts/build-control-plane.py'
            with patch.object(sys,'argv',[str(script),'--output',td+'/image.tar']), patch('subprocess.check_output',side_effect=['a'*40+'\n','']), patch('subprocess.run') as run:
                runpy.run_path(str(script),run_name='__main__')
            command=run.call_args.args[0]
            self.assertIn('python3,/opt/vmweave/control/control_plane.py',command)
            self.assertNotIn('VMWEAVE_MODE=review',command)
            with tarfile.open(Path(td)/'control-plane-layer.tar') as archive:
                self.assertTrue(archive.getmember('opt/vmweave/control/control_plane.py').isfile())
                self.assertTrue(archive.getmember('opt/vmweave/control/vmweave_env.py').isfile())
                alias=archive.getmember('opt/flyt/control/control_plane.py')
                self.assertTrue(alias.issym())
                self.assertEqual(alias.linkname,'/opt/vmweave/control/control_plane.py')

if __name__=='__main__':unittest.main()
