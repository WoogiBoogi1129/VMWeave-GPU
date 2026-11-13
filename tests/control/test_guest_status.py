import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'runtime/shm/control'))
from guest_status import Publisher
from provision import make_layout

class Fake:
    def __init__(self, owner=False):
        self.owner_mode=owner; self.failed=False; self.lock=threading.Lock()
        self.last_success=time.time(); self.calls=[]
    def exchange(self, api, data, capacity):
        self.calls.append(api); self.last_success=time.time(); return 0,b''

class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        layout,_=make_layout('1'*32,'2'*32,['3'*32]);(self.root/'layout').write_bytes(layout)
        (self.root/'library').write_bytes(b'fixture-library')
    def publisher(self,t):
        return Publisher(self.root/'state/status.json',t,self.root/'library',self.root/'layout',self.root/'gpu.sock')
    def read(self):return json.loads((self.root/'state/status.json').read_text())
    def test_idle_legacy_only_heartbeat_no_session_open(self):
        t=Fake();p=self.publisher(t);p.tick();self.assertEqual(t.calls,[3]);self.assertTrue(self.read()['ready'])
    def test_busy_client_is_healthy_without_transport_probe(self):
        t=Fake();p=self.publisher(t);t.lock.acquire()
        try:p.tick();self.assertEqual(t.calls,[]);self.assertTrue(self.read()['ready']);self.assertTrue(self.read()['activeClient'])
        finally:t.lock.release()
    def test_native_owner_never_called_from_publisher(self):
        t=Fake(owner=True);p=self.publisher(t);p.tick();self.assertEqual(t.calls,[])
        t.last_success-=20;p.tick();self.assertFalse(self.read()['ready'])
    def test_failed_and_stopped_fence_discovery(self):
        t=Fake();p=self.publisher(t);t.failed=True;p.tick();self.assertFalse(self.read()['ready']);self.assertEqual(t.calls,[])
        p.close();self.assertEqual(self.read()['reason'],'stopped')
    def test_atomic_replacement_and_identity(self):
        t=Fake();p=self.publisher(t);old=os.open(p.path,os.O_RDONLY)
        try:p.tick();self.assertFalse(json.loads(os.read(old,8192))['ready']);self.assertTrue(self.read()['ready'])
        finally:os.close(old)
        self.assertEqual(self.read()['generation'],'2'*32)
        self.assertEqual(self.read()['allocation'],'1'*32)
        self.assertEqual(p.path.stat().st_mode & 0o777,0o644)
    def test_two_slots_have_distinct_binding(self):
        layout,_=make_layout('1'*32,'2'*32,['3'*32,'4'*32]);(self.root/'layout').write_bytes(layout)
        for slot in (0,1):
            p=Publisher(self.root/f'state/{slot}/status.json',Fake(),self.root/'library',self.root/'layout',self.root/'gpu.sock',slot)
            p.tick(); d=json.loads(p.path.read_text())
            self.assertEqual((d['schemaVersion'],d['slotCount'],d['slotIndex']),(2,2,slot))
            self.assertEqual(d['sessionID'],str(slot+3)*32)
        with self.assertRaises(ValueError):
            Publisher(self.root/'invalid',Fake(),self.root/'library',self.root/'layout',self.root/'gpu.sock',2)
    def test_invalid_layouts_rejected(self):
        from guest_status import read_layout
        layout,_=make_layout('1'*32,'2'*32,['3'*32,'4'*32])
        bad=list([layout[:-1],layout+b'x',layout[:144]+layout[64:144],b''])
        for data in bad:
            (self.root/'layout').write_bytes(data)
            with self.assertRaises(ValueError):read_layout(self.root/'layout')
