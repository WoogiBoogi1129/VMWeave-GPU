import importlib.util
from pathlib import Path
import socket
import threading
import unittest

spec = importlib.util.spec_from_file_location('broker', Path(__file__).resolve().parents[2] / 'runtime/shm/control/guest_broker.py')
broker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(broker)

class Fake(broker.Transport):
    def __init__(self):
        self.lock = threading.Lock()
        self.failed = False
        self.events = []
        self.close_error = False
    def exchange(self, api, data, capacity):
        self.events.append((api, data))
        if api == broker.CLOSE and self.close_error:
            raise RuntimeError('broken transport')
        return 0, b''

class BrokerTests(unittest.TestCase):
    def session(self, transport, abrupt=False):
        client, server = socket.socketpair()
        thread = threading.Thread(target=transport.serve, args=(server,))
        thread.start()
        client.sendall(broker.REQUEST.pack(broker.MAGIC, 0x1001, 0, 0))
        self.assertEqual(broker.RESPONSE.unpack(broker.receive(client,16)), (broker.MAGIC,0,0))
        if not abrupt:
            client.sendall(broker.REQUEST.pack(broker.MAGIC,2,0,0))
            self.assertEqual(broker.RESPONSE.unpack(broker.receive(client,16)), (broker.MAGIC,0,0))
        client.close()
        thread.join(2)
        self.assertFalse(thread.is_alive())
    def test_sequential_and_killed_clients_get_new_epochs(self):
        t=Fake()
        self.session(t)
        self.session(t, abrupt=True)
        self.session(t)
        self.assertEqual([e[0] for e in t.events], [4,6,5]*3)
        epochs=[data for api,data in t.events if api==4]
        self.assertEqual(len(set(epochs)),3)
        self.assertFalse(t.failed)
    def test_busy_client_cannot_close_owner(self):
        t=Fake();t.lock.acquire()
        a,b=socket.socketpair()
        t.serve(b)
        self.assertEqual(broker.RESPONSE.unpack(broker.receive(a,16)),(broker.MAGIC,46,0))
        self.assertTrue(t.lock.locked());self.assertEqual(t.events,[])
        a.close();t.lock.release()
    def test_failed_close_fences_future_clients_and_unlocks(self):
        t=Fake();t.close_error=True
        a,b=socket.socketpair();a.close()
        with self.assertRaises(RuntimeError):t.serve(b)
        self.assertTrue(t.failed);self.assertFalse(t.lock.locked())

if __name__=='__main__': unittest.main()
