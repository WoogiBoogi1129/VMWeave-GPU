"""Prepared tests of real Python Broker buffer/gather paths. Not run at preparation."""
import ctypes as C
import importlib.util
import mmap
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'source'
sys.path.insert(0, str(ROOT / 'runtime/shm/control'))
spec = importlib.util.spec_from_file_location('candidate_broker', ROOT / 'runtime/shm/control/guest_broker.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


class BrokerBuffers(unittest.TestCase):
    def make(self, gather):
        obj = b.Transport.__new__(b.Transport)
        obj.reuse = True
        obj.scratch = {}
        obj.seen = []
        def call(api, data, n, out, cap, got):
            obj.seen.append(C.string_at(data, n))
            got._obj.value = 0
            return 0
        def parts(api, head, nh, tail, nt, out, cap, got):
            obj.seen.append(C.string_at(head, nh) + C.string_at(tail, nt))
            got._obj.value = 0
            return 0
        obj.call = call
        obj.parts = parts if gather else None
        return obj

    def test_gather_matches_staging_and_reused_logical_lengths(self):
        for gather in (False, True):
            obj = self.make(gather)
            with mmap.mmap(-1, 2*b.BULK_BYTES) as arena:
                for size in (1048576, 32, 4096):
                    arena[:size] = bytes([size % 251])*size
                    desc = struct.pack('<IIQQQQQ', 1, 0, 7, 0, 0, 0, size)
                    self.assertEqual(obj.bulk_copy(b'e'*16, desc, 0, arena), (0, 0))
                    self.assertEqual(obj.seen[-1], b'e'*16 + struct.pack('<II', 0x1012, 0) + desc + arena[:size])
                if gather:
                    self.assertEqual(C.sizeof(obj.scratch['request']), 72)
                else:
                    self.assertEqual(C.sizeof(obj.scratch['request']), 72+1048576)
            # mmap closes successfully: no exported buffer reference survives.

    def test_output_only_valid_prefix(self):
        obj = self.make(False)
        def call(api, data, n, out, cap, got):
            C.memmove(out, b'ok', 2); got._obj.value = 2; return 0
        obj.call = call
        self.assertEqual(obj.exchange(99, b'', 4096), (0, b'ok'))
        self.assertEqual(obj.exchange(99, b'', 4), (0, b'ok'))
        self.assertEqual(C.sizeof(obj.scratch['output']), 4096)

    def test_bad_metadata_does_not_call_transport(self):
        obj = self.make(True)
        with mmap.mmap(-1, 2*b.BULK_BYTES) as arena:
            for desc in (b'', struct.pack('<IIQQQQQ', 1, 1, 7, 0, 0, 0, 64),
                         struct.pack('<IIQQQQQ', 1, 0, 7, 0, 0, 0, b.BULK_BYTES+1)):
                with self.assertRaises(ValueError): obj.bulk_copy(b'e'*16, desc, 0, arena)
        self.assertFalse(obj.seen)


if __name__ == '__main__':
    unittest.main()
