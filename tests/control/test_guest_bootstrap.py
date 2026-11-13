"""Real child processes: slot env, peer survival and service shutdown."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
CONTROL=Path(__file__).resolve().parents[2]/'runtime/shm/control'

class BootstrapTests(unittest.TestCase):
    def test_child_failure_isolated_and_shutdown_reaps_peer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'fake.py').write_text('''import os,sys,time
from pathlib import Path
root=Path(os.environ['TEST_ROOT'])
slot=os.environ['VMWEAVE_SLOT']
(root/('child-'+slot)).write_text(str(os.getpid()))
(root/('args-'+slot)).write_text(' '.join(sys.argv))
if slot=='0':raise SystemExit(7)
while True:time.sleep(.05)
''')
            code=f"import sys;sys.path.insert(0,{str(CONTROL)!r});from guest_bootstrap import run_brokers;from pathlib import Path;import os;os.umask(0o007);raise SystemExit(run_brokers(2,os.environ,Path({str(root/'broker')!r}),Path({str(root/'state')!r}),{str(root/'fake.py')!r}))"
            p=subprocess.Popen([sys.executable,'-c',code],env=dict(os.environ,TEST_ROOT=tmp))
            try:
                deadline=time.monotonic()+5
                while not (root/'child-1').exists() and time.monotonic()<deadline:time.sleep(.05)
                pid=int((root/'child-1').read_text());time.sleep(.3)
                self.assertIsNone(p.poll());os.kill(pid,0)
                for d in [root/"broker/slots",root/"broker/slots/1",root/"state/slots"]:
                    self.assertEqual(d.stat().st_mode & 0o022,0)
                for slot in (0,1):self.assertIn(f'slots/{slot}/gpu.sock',(root/f'args-{slot}').read_text())
                p.terminate();self.assertEqual(p.wait(timeout=5),0)
                with self.assertRaises(ProcessLookupError):os.kill(pid,0)
            finally:
                if p.poll() is None:p.kill();p.wait()
