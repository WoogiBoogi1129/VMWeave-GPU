"""Future CPU integration suite: real C direct descriptor path with old/new Broker."""
import test_bulk_copy as base
import unittest
from unittest.mock import patch

DIRECT_PROBE = base.PROBE.replace("rc=call(0x1012,payload,len(payload),out,cap,ctypes.byref(got));assert rc==0,rc", """if struct.unpack_from('<I',payload)[0]==1 and n>=1048576:
  direct=lib.vmweave_broker_copy_direct
  direct.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)]
  direct.restype=ctypes.c_int
  rc=direct(payload[:48],payload[48:],n,ctypes.byref(got))
 else:
  rc=call(0x1012,payload,len(payload),out,cap,ctypes.byref(got))
 assert rc==0,rc""")
class DirectTests(base.BulkTests):
    def setUp(self):
        override = patch.object(base, "PROBE", DIRECT_PROBE)
        override.start()
        self.addCleanup(override.stop)
        super().setUp()
if __name__=='__main__': unittest.main()
