"""Capture a terminal Channel event even when Allocation objects auto-delete."""
import json
import queue
import subprocess
import threading
import time
from urllib.parse import urlencode


class ReleaseWatch:
    def __init__(self, channel):
        self.initial = channel
        self.uid = channel['metadata']['uid']
        m = channel['metadata']
        query = urlencode({'watch': 'true', 'resourceVersion': m['resourceVersion'],
                           'fieldSelector': 'metadata.name=' + m['name'], 'timeoutSeconds': '600'})
        resource = channel['kind'].lower() + 's'
        url = '/apis/' + channel['apiVersion'] + '/namespaces/' + m['namespace'] + '/' + resource + '?' + query
        self.events = queue.Queue()
        self.proc = subprocess.Popen(['kubectl', 'get', '--raw', url], stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True)
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        try:
            for line in self.proc.stdout:
                self.events.put(json.loads(line))
        except Exception as exc:
            self.events.put(exc)
        finally:
            self.events.put(EOFError('Channel watch ended before release'))

    def wait(self, timeout=300):
        if self.initial.get('status', {}).get('phase') == 'Released':
            return self.initial
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Channel did not release')
            try:
                event = self.events.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutError('Channel did not release') from exc
            if isinstance(event, Exception):
                raise event
            obj = event.get('object', {})
            if event.get('type') == 'ERROR':
                raise RuntimeError('Channel watch failed: ' + str(obj))
            if obj.get('metadata', {}).get('uid') != self.uid:
                continue
            if obj.get('status', {}).get('phase') == 'Released':
                return obj
            if event.get('type') == 'DELETED':
                raise RuntimeError('Channel disappeared without Released evidence')

    def close(self):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5)
        self.thread.join(timeout=5)
        self.proc.stdout.close()
        self.proc.stderr.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
