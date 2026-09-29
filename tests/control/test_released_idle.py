import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'runtime/shm/control'))
from control_plane import process

class ReleasedIdle(unittest.TestCase):
    def test_released_history_does_not_reconcile(self):
        with patch('channel_controller.reconcile') as reconcile:
            process(object(), {'metadata':{'name':'old'},'status':{'phase':'Released'}}, 'active')
            reconcile.assert_not_called()

    def test_released_deletion_keeps_finalizer_reconciliation(self):
        c={'metadata':{'name':'old','deletionTimestamp':'2026-09-28T00:00:00Z'},'status':{'phase':'Released'}}
        with patch('channel_controller.reconcile') as reconcile:
            api=object();process(api,c,'active');reconcile.assert_called_once_with(api,c)

if __name__=='__main__':unittest.main()
