#!/usr/bin/env python3
"""Render new lab inputs offline. Never installs or modifies an Operator."""
import argparse
import ipaddress
import json
from pathlib import Path
import re
import secrets
import uuid

EXP = Path(__file__).resolve().parents[1]
REPO = EXP.parents[1]


def render(config):
    c = dict(config)
    for key, value in c.items():
        if isinstance(value, str) and 'REPLACE' in value:
            raise ValueError('Unconfigured field: ' + key)
    for key in ('prefix', 'namespace', 'node'):
        if not re.fullmatch(r'[a-z0-9](?:[-a-z0-9]*[a-z0-9])?', c[key]):
            raise ValueError('Invalid Kubernetes name: ' + key)
    if len(c['prefix']) > 40 or c['namespace'] in ('vmweave-system', 'vmweave-nested-k8s', 'vmweave-nested-system'):
        raise ValueError('Use a short new prefix and an existing centrally managed workload namespace')
    if not re.fullmatch(r'GPU-[a-fA-F0-9-]{36}', c['gpu_uuid']):
        raise ValueError('A concrete approved GPU UUID is required')
    if not 1 <= c['compute'] <= 100 or c['memory_mib'] <= 0:
        raise ValueError('Invalid quota')
    if not 576 < c['wireguard_mtu'] <= 9000:
        raise ValueError('Invalid MTU')
    networks = [ipaddress.IPv4Network(c[k]) for k in ('node_cidr', 'pod_cidr', 'service_cidr')]
    if any(a.overlaps(b) for i, a in enumerate(networks) for b in networks[i+1:]):
        raise ValueError('Lab CIDRs overlap')
    if c['cp_ip'] == c['worker_ip'] or any(ipaddress.IPv4Address(c[k]) not in networks[0] for k in ('cp_ip', 'worker_ip')):
        raise ValueError('Node addresses must be distinct and in node_cidr')
    pvroot = Path(c['pv_root'])
    if not pvroot.is_absolute() or pvroot == Path('/'):
        raise ValueError('Use a dedicated absolute PV root')
    public = Path(c['ssh_public_key']).read_text().strip()
    if '\n' in public or not public.startswith(('ssh-ed25519 ', 'ssh-rsa ')):
        raise ValueError('Supply one SSH public key, never a private key')
    lockpath = Path(c['release_lock'])
    if not lockpath.is_absolute():
        lockpath = REPO / lockpath
    lock = json.loads(lockpath.read_text())
    for key in ('operator', 'helper', 'worker', 'hook', 'guest-artifacts'):
        if not re.fullmatch(r'.+@sha256:[a-f0-9]{64}', lock['images'][key]):
            raise ValueError('Digest-pinned release images required: ' + key)
    ns, prefix = c['namespace'], c['prefix']
    storage, vms = [], []
    for role, size, ram in [('cp', '40Gi', '8Gi'), ('worker', '80Gi', '16Gi'), ('shm', '1Gi', None)]:
        name = prefix + '-' + role + ('-root' if ram else '')
        meta = {'name': name, 'labels': {'vmweave-lab': prefix}}
        storage.append({'apiVersion': 'v1', 'kind': 'PersistentVolume', 'metadata': meta, 'spec': {
            'capacity': {'storage': size}, 'accessModes': ['ReadWriteOnce'], 'volumeMode': 'Filesystem',
            'persistentVolumeReclaimPolicy': 'Retain', 'storageClassName': '',
            'claimRef': {'namespace': ns, 'name': name}, 'local': {'path': str(pvroot / role)},
            'nodeAffinity': {'required': {'nodeSelectorTerms': [{'matchExpressions': [
                {'key': 'kubernetes.io/hostname', 'operator': 'In', 'values': [c['node']]}]}]}}}})
        storage.append({'apiVersion': 'v1', 'kind': 'PersistentVolumeClaim', 'metadata': {**meta, 'namespace': ns},
                        'spec': {'accessModes': ['ReadWriteOnce'], 'volumeMode': 'Filesystem', 'storageClassName': '',
                                 'volumeName': name, 'resources': {'requests': {'storage': size}}}})
        if not ram:
            continue
        vm = prefix + '-' + role
        mac = '02:' + ':'.join(f'{b:02x}' for b in secrets.token_bytes(5))
        user = (f'#cloud-config\nhostname: {vm}\nmanage_etc_hosts: true\nssh_pwauth: false\n'
                f'users:\n  - name: ubuntu\n    sudo: ALL=(ALL) NOPASSWD:ALL\n    shell: /bin/bash\n'
                f'    ssh_authorized_keys:\n      - {public}\ngrowpart:\n  mode: auto\n  devices: ["/"]\nresize_rootfs: true\n')
        network = f'version: 2\nethernets:\n  eth0:\n    match:\n      macaddress: "{mac}"\n    set-name: eth0\n    dhcp4: true\n'
        vms.append({'apiVersion': 'kubevirt.io/v1', 'kind': 'VirtualMachine',
            'metadata': {'name': vm, 'namespace': ns, 'labels': {'vmweave-lab': prefix}},
            'spec': {'runStrategy': 'Halted', 'template': {'metadata': {'labels': {'central-lab-vm': vm}}, 'spec': {
                'nodeSelector': {'kubernetes.io/hostname': c['node']},
                'domain': {'cpu': {'cores': 4}, 'resources': {'requests': {'cpu': '4', 'memory': ram}},
                    'machine': {'type': 'q35'}, 'firmware': {'uuid': str(uuid.uuid4())}, 'devices': {
                        'disks': [{'name': n, 'disk': {'bus': 'virtio'}} for n in ('root', 'cloudinit')],
                        'interfaces': [{'name': 'default', 'masquerade': {}, 'macAddress': mac}]}},
                'networks': [{'name': 'default', 'pod': {}}], 'volumes': [
                    {'name': 'root', 'persistentVolumeClaim': {'claimName': name}},
                    {'name': 'cloudinit', 'cloudInitNoCloud': {'userData': user, 'networkData': network}}]}}}})
        vms.append({'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': vm, 'namespace': ns, 'labels': {'vmweave-lab': prefix}},
            'spec': {'selector': {'central-lab-vm': vm}, 'ports': [
                {'name': 'ssh', 'port': 22, 'targetPort': 22},
                {'name': 'wireguard', 'port': 51820, 'targetPort': 51820, 'protocol': 'UDP'}]}})
    profile = {'apiVersion': 'vmweave.io/v1alpha1', 'kind': 'GPUProfile',
        'metadata': {'name': prefix + '-gpu', 'namespace': ns, 'labels': {'vmweave-lab': prefix}},
        'spec': {'approved': False, 'backend': 'hami', 'cores': c['compute'], 'memoryMiB': c['memory_mib'],
            'maxClients': 1, 'nodeName': c['node'], 'gpuUUID': c['gpu_uuid'], 'hamiNamespace': 'kube-system',
            'runtimeClass': 'nvidia', 'schedulerName': 'hami-scheduler', 'workerImage': lock['images']['worker']}}
    outputs = {'config.json': json.dumps(c, indent=2), 'release-lock.json': json.dumps(lock, indent=2),
               'storage.json': json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': storage}, indent=2),
               'vms.json': json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': vms}, indent=2),
               'profile.json': json.dumps(profile, indent=2)}
    replacements = {'vw-k8s-cp-01': prefix+'-cp', 'vw-k8s-worker-01': prefix+'-worker',
        '10.245.0.10': c['cp_ip'], '10.245.0.11': c['worker_ip'], '10.246.0.0/16': c['pod_cidr'],
        '10.247.0.0/16': c['service_cidr'], 'clusterName: vmweave-nested': 'clusterName: '+prefix}
    for file in ('init.yaml', 'cilium-values.yaml'):
        content = (EXP/'manifests'/file).read_text()
        for old, new in replacements.items():
            content = content.replace(old, new)
        if file == 'cilium-values.yaml':
            content = content.replace('MTU: 1220', 'MTU: '+str(c['wireguard_mtu']))
        outputs[file] = content
    for file in ('k8s-setup.sh', 'k8s-worker-setup.sh'):
        outputs[file] = (EXP/'installation'/file).read_text().replace('/home/ubuntu/nested', '/home/ubuntu/central-lab')
    return outputs


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    files = render(json.loads(args.config.read_text()))
    args.output.mkdir(parents=True, exist_ok=False)
    for name, content in files.items():
        (args.output/name).write_text(content.rstrip('\n')+'\n')
    print(f'Rendered {len(files)} local files; no cluster mutation or Operator installation.')
