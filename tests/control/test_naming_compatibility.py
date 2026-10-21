"""Migration contract: new names win, legacy ABI/state remain shared."""
import ctypes
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('env_compat',ROOT/'runtime/shm/control/vmweave_env.py')
env=importlib.util.module_from_spec(spec);spec.loader.exec_module(env)

class EnvironmentTests(unittest.TestCase):
    def test_python_precedence_and_pop(self):
        with patch.dict(os.environ,{'FLYT_STATE_CACHE':'1'},clear=True):
            self.assertEqual(env.get('VMWEAVE_STATE_CACHE'),'1')
            for value in ('0',''):
                os.environ['VMWEAVE_STATE_CACHE']=value
                self.assertEqual(env.require('VMWEAVE_STATE_CACHE'),value)
            env.pop('VMWEAVE_STATE_CACHE')
            self.assertIsNone(env.get('VMWEAVE_STATE_CACHE'))
            with self.assertRaises(KeyError):env.require('VMWEAVE_STATE_CACHE')
    def test_c_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'env.c';binary=Path(tmp)/'env'
            source.write_text('#include "vmweave_env.h"\n#include <stdio.h>\nint main(void){const char *v=vmweave_getenv("VMWEAVE_STATE_CACHE");puts(v?v:"absent");}\n')
            subprocess.run(['cc','-Wall','-Wextra','-Werror','-I',str(ROOT/'runtime/shm/shm-contract/include'),str(source),'-o',str(binary)],check=True)
            for values,expected in [({},'absent'),({'FLYT_STATE_CACHE':'1'},'1'),({'FLYT_STATE_CACHE':'1','VMWEAVE_STATE_CACHE':'0'},'0'),({'FLYT_STATE_CACHE':'1','VMWEAVE_STATE_CACHE':''},'')]:
                self.assertEqual(subprocess.check_output([str(binary)],env=values,text=True).rstrip('\n'),expected)
    def test_legacy_header_and_wire_magic(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'old.c';binary=Path(tmp)/'old'
            source.write_text('#include "flyt_sessions.h"\n#include "flyt_shm_contract.h"\n_Static_assert(FLYT_SESSION_CALL==VMWEAVE_SESSION_CALL,"id changed");\nint main(void){return FLYT_SESSION_CALL!=6;}\n')
            subprocess.run(['cc','-Wall','-Werror','-I',str(ROOT/'runtime/shm/include'),'-I',str(ROOT/'runtime/shm/shm-contract/include'),str(source),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)
        self.assertIn("b'FLYTCHN1'",(ROOT/'runtime/shm/control/provision.py').read_text())
        self.assertIn('FLYTSHM1',(ROOT/'runtime/shm/shm-contract/include/vmweave_shm_contract.h').read_text())
    @unittest.skipUnless(os.getenv('VMWEAVE_TEST_GUEST_LIBRARY'),'requires built Guest library')
    def test_abi_aliases_have_identical_addresses(self):
        lib=ctypes.CDLL(os.environ['VMWEAVE_TEST_GUEST_LIBRARY'])
        for name in ('guest_exchange','broker_exchange','broker_close','broker_cache_stats','guest_lock','shm_open'):
            old=ctypes.cast(getattr(lib,'flyt_'+name),ctypes.c_void_p).value
            new=ctypes.cast(getattr(lib,'vmweave_'+name),ctypes.c_void_p).value
            self.assertEqual(old,new,name)

if __name__=='__main__':unittest.main()
