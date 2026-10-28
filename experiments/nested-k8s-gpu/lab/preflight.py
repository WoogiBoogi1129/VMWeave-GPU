#!/usr/bin/env python3
"""Read-only check that BOTH existing central components manage the lab namespace."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess


def matches(selector, labels):
    if any(labels.get(k) != v for k, v in selector.get('matchLabels', {}).items()):
        return False
    for item in selector.get('matchExpressions', []):
        key, op, values = item['key'], item['operator'], item.get('values', [])
        if op == 'In' and labels.get(key) not in values:
            return False
        if op == 'NotIn' and labels.get(key) in values:
            return False
        if op == 'Exists' and key not in labels:
            return False
        if op == 'DoesNotExist' and key in labels:
            return False
        if op not in ('In', 'NotIn', 'Exists', 'DoesNotExist'):
            raise ValueError('Unsupported selector operator')
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--context', required=True)
    p.add_argument('--namespace', required=True)
    p.add_argument('--release-lock', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        p.error('use a fresh snapshot path')
    def k(*args):
        return json.loads(subprocess.check_output(['kubectl', '--context', a.context, *args, '-o', 'json'], text=True))
    image = json.loads(a.release_lock.read_text())['images']['operator']
    assert '@sha256:' in image, 'pin a release compatible with the currently deployed Operator'
    labels = k('get', 'namespace', a.namespace)['metadata'].get('labels', {})
    deployments = k('get', 'deployments', '-n', 'vmweave-system')['items']
    components = {}
    for d in deployments:
        for c in d['spec']['template']['spec']['containers']:
            args = c.get('args', [])
            for role in ('controller', 'webhook'):
                if '--component='+role not in args:
                    continue
                assert role not in components, 'multiple central '+role+' deployments; inspect ownership'
                scope = next(x.split('=', 1)[1].split(',') for x in args if x.startswith('--namespaces='))
                assert a.namespace in scope and '--mode=active' in args, 'namespace not managed in active mode'
                assert c['image'] == image, 'running Operator differs from release lock; do not silently downgrade/upgrade'
                assert d['status'].get('observedGeneration', 0) >= d['metadata']['generation']
                assert d['status'].get('availableReplicas', 0) >= 1
                components[role] = {'name': d['metadata']['name'], 'uid': d['metadata']['uid'], 'image': image,
                    'args': args, 'serviceAccount': d['spec']['template']['spec']['serviceAccountName'],
                    'generation': d['metadata']['generation'], 'podSelector': d['spec']['selector']}
    assert set(components) == {'controller', 'webhook'}, 'both existing central components required'
    hooks = []
    for v in k('get', 'validatingwebhookconfigurations')['items']:
        for w in v['webhooks']:
            if not any('vmweave.io' in r.get('apiGroups', []) for r in w.get('rules', [])):
                continue
            if not matches(w.get('namespaceSelector', {}), labels):
                continue
            service = w.get('clientConfig', {}).get('service', {})
            assert service.get('namespace') == 'vmweave-system', 'another VMWeave webhook also matches this namespace'
            assert not w.get('objectSelector') and not w.get('matchConditions'), 'custom admission filtering requires review'
            assert w.get('failurePolicy') == 'Fail' and w['clientConfig'].get('caBundle')
            svc = k('get', 'service', service['name'], '-n', 'vmweave-system')
            pod_labels = next(d['spec']['template']['metadata']['labels'] for d in deployments if d['metadata']['name'] == components['webhook']['name'])
            assert svc['spec'].get('selector') and all(pod_labels.get(key) == value for key, value in svc['spec']['selector'].items())
            hooks.append({'configuration': v['metadata']['name'], 'name': w['name'], 'service': service,
                          'namespaceSelector': w.get('namespaceSelector'), 'failurePolicy': w['failurePolicy']})
    assert hooks, 'no existing central VMWeave admission route'
    bindings = k('get', 'rolebindings', '-n', a.namespace)['items']
    for role, info in components.items():
        assert any(any(s.get('kind') == 'ServiceAccount' and s.get('namespace') == 'vmweave-system' and
                       s.get('name') == info['serviceAccount'] for s in b.get('subjects', [])) for b in bindings), 'missing central '+role+' RoleBinding'
    # A non-central active controller must not also watch this namespace.
    for d in k('get', 'deployments', '-A')['items']:
        if d['metadata']['namespace'] == 'vmweave-system' or not d['spec'].get('replicas', 1):
            continue
        for c in d['spec']['template']['spec']['containers']:
            args = c.get('args', [])
            if '--component=controller' in args and '--mode=active' in args:
                scopes = [x.split('=', 1)[1].split(',') for x in args if x.startswith('--namespaces=')]
                assert scopes and all(a.namespace not in scope for scope in scopes), 'overlapping/unknown active controller scope'
    pods = k('get', 'pods', '-n', 'vmweave-system')['items']
    for role, info in components.items():
        ready = [pod for pod in pods if matches(info['podSelector'], pod['metadata'].get('labels', {}))
                 and any(c['type'] == 'Ready' and c['status'] == 'True' for c in pod['status'].get('conditions', []))]
        assert ready, 'no Ready '+role+' Pod'
        info['pods'] = [{'name': pod['metadata']['name'], 'uid': pod['metadata']['uid'],
                        'containers': pod['status'].get('containerStatuses', [])} for pod in ready]
    result = {'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'namespace': a.namespace,
              'context': a.context, 'result': 'PASS', 'scope': 'read-only ownership/readiness preflight, not a VM/GPU lab result',
              'components': components, 'admission': hooks}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: existing vmweave-system controller/webhook scope, image, readiness, RBAC binding and admission route')


if __name__ == '__main__':
    main()
