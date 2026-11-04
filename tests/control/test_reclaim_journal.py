"""Fault injection for the exact helper embedded in the published controller."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('reclaim_helper', ROOT/'operator/internal/engine/reclaim_helper.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)

class MemoryJournal:
    def __init__(self):
        self.progress = {'phase': 'Authorized'}
        self.failure = None
    def read(self):
        return copy.deepcopy(self.progress)
    def write(self, p):
        if self.failure == (p['phase'], 'before'):
            raise OSError('API unavailable before commit')
        self.progress = copy.deepcopy(p)
        if self.failure == (p['phase'], 'after'):
            raise OSError('API response lost after commit')

class ReclaimJournalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.identity = {'allocation': '1'*32, 'generation': '2'*32}
        self.target = self.root/self.identity['allocation']
        self.target.mkdir()
        (self.target/'channel').write_bytes(b'backing')
        (self.target/'layout.bin').write_bytes(b'layout')
        (self.target/'ready.json').write_text(json.dumps({'allocationId': self.identity['allocation'], 'generation': self.identity['generation']}))
        self.journal = MemoryJournal()
    def run_reclaim(self, hook=lambda _: None):
        helper.reclaim(str(self.root), self.identity, self.journal, hook)
    def interrupt(self, point):
        def stop(current):
            if current == point:
                raise InterruptedError(point)
        with self.assertRaises(InterruptedError):
            self.run_reclaim(stop)
    def test_all_crash_windows_resume(self):
        for point in ['before_prepare', 'prepared', 'unlinked_channel', 'unlinked_layout.bin', 'unlinked_ready.json', 'removed_directory', 'before_complete', 'complete']:
            with self.subTest(point=point):
                case = ReclaimJournalTest('runTest')
                case.setUp()
                try:
                    case.interrupt(point)
                    case.run_reclaim()
                    self.assertFalse(case.target.exists())
                    self.assertEqual(case.journal.progress['phase'], 'Complete')
                    case.run_reclaim()  # repeated execution after completion
                finally:
                    case.doCleanups()
    def test_api_failure_before_or_after_each_write(self):
        for phase in ['Prepared', 'Complete']:
            for side in ['before', 'after']:
                with self.subTest(phase=phase, side=side):
                    case = ReclaimJournalTest('runTest'); case.setUp()
                    try:
                        case.journal.failure = (phase, side)
                        with self.assertRaises(OSError): case.run_reclaim()
                        if phase == 'Prepared': self.assertEqual(set(os.listdir(case.target)), set(helper.FILES))
                        case.journal.failure = None; case.run_reclaim()
                        self.assertEqual(case.journal.progress['phase'], 'Complete')
                        self.assertFalse(case.target.exists())
                    finally: case.doCleanups()
    def test_absence_alone_is_not_completion(self):
        for p in self.target.iterdir(): p.unlink()
        self.target.rmdir()
        with self.assertRaises(ValueError): self.run_reclaim()
        self.assertEqual(self.journal.progress['phase'], 'Authorized')
    def test_partial_without_prepared_evidence_fails(self):
        (self.target/'channel').unlink()
        with self.assertRaises(ValueError): self.run_reclaim()
        self.assertTrue((self.target/'ready.json').exists())
    def test_replaced_directory_fails(self):
        self.interrupt('prepared')
        self.target.rename(self.root/'old')
        self.target.mkdir()
        with self.assertRaises(ValueError): self.run_reclaim()
    def test_replaced_file_fails_before_further_deletion(self):
        self.interrupt('prepared')
        p = self.target/'layout.bin'; p.rename(self.root/'old-layout'); p.write_bytes(b'layout')
        with self.assertRaises(ValueError): self.run_reclaim()
        self.assertTrue((self.target/'channel').exists())
    def test_symlink_hardlink_and_extra_file_fail(self):
        self.interrupt('prepared')
        (self.target/'extra').write_text('extra')
        with self.assertRaises(ValueError): self.run_reclaim()
        (self.target/'extra').unlink()
        os.link(self.target/'channel', self.root/'linked')
        with self.assertRaises(ValueError): self.run_reclaim()
        (self.root/'linked').unlink()
        (self.target/'layout.bin').unlink(); (self.target/'layout.bin').symlink_to(self.root/'linked')
        with self.assertRaises(ValueError): self.run_reclaim()
        self.assertTrue((self.target/'channel').exists())
    def test_wrong_generation_fails(self):
        self.identity['generation'] = '3'*32
        with self.assertRaises(ValueError): self.run_reclaim()
        self.assertEqual(self.journal.progress['phase'], 'Authorized')
    def test_corrupt_prepared_inventory_fails_even_when_absent(self):
        for p in self.target.iterdir(): p.unlink()
        self.target.rmdir()
        self.journal.progress = {'phase': 'Prepared'}
        with self.assertRaises(ValueError): self.run_reclaim()
    def test_other_allocation_is_untouched(self):
        other = self.root/('3'*32); other.mkdir(); (other/'channel').write_bytes(b'keep')
        self.run_reclaim()
        self.assertEqual((other/'channel').read_bytes(), b'keep')

if __name__ == '__main__': unittest.main()
