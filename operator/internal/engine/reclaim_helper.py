"""Controller-embedded, least-privilege reclamation helper (stdlib only).

The API journal is written BEFORE the first unlink. Worker credentials cannot
write it. No local file or Pod status is accepted as completion evidence.
"""
import json
import os
import re
import ssl
import stat
import sys
import urllib.request

FILES = ('channel', 'layout.bin', 'ready.json')


def fingerprint(st):
    return {'inode': st.st_ino, 'size': st.st_size, 'mode': stat.S_IMODE(st.st_mode),
            'uid': st.st_uid, 'gid': st.st_gid}


def regular(directory, name):
    st = os.stat(name, dir_fd=directory, follow_symlinks=False)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        raise ValueError('unsafe allocation entry')
    return fingerprint(st)


def reclaim(root, identity, journal, checkpoint=lambda _: None):
    allocation, generation = identity['allocation'], identity['generation']
    for value in (allocation, generation):
        if not re.fullmatch('[0-9a-f]{32}', value) or int(value, 16) == 0:
            raise ValueError('invalid allocation identity')
    progress = journal.read()
    if progress['phase'] == 'Complete':
        return
    if progress['phase'] not in ('Authorized', 'Prepared'):
        raise ValueError('invalid journal phase')
    if progress['phase'] == 'Prepared':
        if not isinstance(progress.get('directoryInode'), int) or progress['directoryInode'] <= 0 or set(progress.get('files', {})) != set(FILES):
            raise ValueError('invalid prepared inventory')
    base = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            directory = os.open(allocation, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=base)
        except FileNotFoundError:
            if progress['phase'] != 'Prepared':
                raise ValueError('missing allocation without prepared evidence')
            directory = None
        if directory is not None:
            try:
                dst = os.fstat(directory)
                names = set(os.listdir(directory))
                if progress['phase'] == 'Authorized':
                    if names != set(FILES):
                        raise ValueError('incomplete allocation without prepared evidence')
                    inventory = {name: regular(directory, name) for name in FILES}
                    fd = os.open('ready.json', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
                    with os.fdopen(fd) as stream:
                        ready = json.load(stream)
                    if ready['allocationId'] != allocation or ready['generation'] != generation:
                        raise ValueError('stale reclamation')
                    progress = {'phase': 'Prepared', 'directoryInode': dst.st_ino, 'files': inventory}
                    checkpoint('before_prepare')
                    journal.write(progress)  # acknowledged API persistence before any deletion
                    checkpoint('prepared')
                if dst.st_ino != progress['directoryInode'] or not names.issubset(FILES):
                    raise ValueError('allocation replaced or unexpected contents')
                # Validate EVERY surviving entry before removing any further entry.
                for name in names:
                    if regular(directory, name) != progress['files'][name]:
                        raise ValueError('allocation entry replaced')
                for name in FILES:
                    if name in names:
                        os.unlink(name, dir_fd=directory)
                        checkpoint('unlinked_' + name)
                os.fsync(directory)
            finally:
                os.close(directory)
            # Refuse a replaced path; the saved inode also covers retries.
            st = os.stat(allocation, dir_fd=base, follow_symlinks=False)
            if not stat.S_ISDIR(st.st_mode) or st.st_ino != progress['directoryInode']:
                raise ValueError('allocation directory replaced')
            os.rmdir(allocation, dir_fd=base)
            checkpoint('removed_directory')
        os.fsync(base)
        checkpoint('before_complete')
        journal.write({**progress, 'phase': 'Complete'})
        checkpoint('complete')
    finally:
        os.close(base)


class APIJournal:
    def __init__(self, namespace, name, uid, authorization):
        self.uid, self.authorization = uid, authorization
        host = os.environ['KUBERNETES_SERVICE_HOST']
        if ':' in host:
            host = '[' + host + ']'
        self.url = 'https://%s:%s/api/v1/namespaces/%s/configmaps/%s' % (
            host, os.environ.get('KUBERNETES_SERVICE_PORT_HTTPS', '443'), namespace, name)
        self.ca = ssl.create_default_context(cafile='/var/run/secrets/kubernetes.io/serviceaccount/ca.crt')

    def request(self, method, body=None):
        with open('/var/run/secrets/kubernetes.io/serviceaccount/token') as stream:
            token = stream.read().strip()
        req = urllib.request.Request(self.url, method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, context=self.ca, timeout=30) as response:
            obj = json.load(response)
        if obj['metadata']['uid'] != self.uid or obj['metadata'].get('deletionTimestamp'):
            raise ValueError('journal identity unavailable')
        if obj['data']['authorization'] != self.authorization:
            raise ValueError('journal authorization changed')
        return obj

    def read(self):
        self.obj = self.request('GET')
        return json.loads(self.obj['data']['progress'])

    def write(self, progress):
        # PUT carries UID/resourceVersion: conflicting or ambiguous updates stop
        # before further filesystem work; a new helper reads the persisted state.
        self.obj['data']['progress'] = json.dumps(progress, sort_keys=True)
        self.obj = self.request('PUT', self.obj)


if __name__ == '__main__':
    root, namespace, name, uid, authorization = sys.argv[1:]
    record = json.loads(authorization)
    reclaim(root, record['identity'], APIJournal(namespace, name, uid, authorization))
