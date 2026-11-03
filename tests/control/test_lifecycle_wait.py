import importlib.util
from pathlib import Path
import queue
import unittest

spec = importlib.util.spec_from_file_location('lifecycle_wait', Path(__file__).resolve().parents[2]/'scripts/operator/lifecycle_wait.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ReleaseWatchTest(unittest.TestCase):
    def watch(self, events):
        w = m.ReleaseWatch.__new__(m.ReleaseWatch)
        w.initial = {'status': {'phase': 'Ready'}}
        w.uid = 'original'
        w.events = queue.Queue()
        for event in events:
            w.events.put(event)
        return w

    def test_terminal_event_survives_fast_delete(self):
        released = {'metadata': {'uid': 'original'}, 'status': {'phase': 'Released', 'completion': {'allocation': 'old'}}}
        w = self.watch([{'type': 'MODIFIED', 'object': released}, {'type': 'DELETED', 'object': released}])
        self.assertEqual(w.wait(.1), released)

    def test_deletion_without_completion_is_not_success(self):
        w = self.watch([{'type': 'DELETED', 'object': {'metadata': {'uid': 'original'}, 'status': {'phase': 'Draining'}}}])
        with self.assertRaises(RuntimeError):
            w.wait(.1)

    def test_same_name_replacement_is_not_release_evidence(self):
        w = self.watch([{'type': 'MODIFIED', 'object': {'metadata': {'uid': 'replacement'}, 'status': {'phase': 'Released'}}}])
        with self.assertRaises(TimeoutError):
            w.wait(.01)

    def test_expired_watch_requires_failure(self):
        w = self.watch([{'type': 'ERROR', 'object': {'code': 410, 'reason': 'Expired'}}])
        with self.assertRaises(RuntimeError):
            w.wait(.1)
