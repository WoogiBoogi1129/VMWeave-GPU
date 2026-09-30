"""Read-only final resource checks after UID-scoped cleanup and monitor retention."""
import hashlib
import urllib.request
from datetime import datetime, timezone
from common import *

validation=json.loads((OUT/'validation.json').read_text())
assert validation['campaign_complete'] and validation['status']=='PASS'
cleanup=json.loads((OUT/'cleanup-resources.json').read_text())
retained=json.loads((OUT/'monitoring/retained.json').read_text())
baseline=json.loads((OUT/'noncampaign-before-cleanup.json').read_text())
preserved=[]
for r in baseline['resources']:
    resource=r['kind']+('.'+r['apiVersion'].split('/')[0] if '/' in r['apiVersion'] else '')
    current=get(resource,r['name'],r['namespace'])
    assert current and current['metadata']['uid']==r['uid'],('Pre-existing resource changed',r)
    digest=hashlib.sha256(json.dumps(current['spec'],sort_keys=True).encode()).hexdigest()
    assert digest==r['spec_sha256'],('Pre-existing specification changed',r)
    preserved.append(r)
remaining=[]
for ns in [NS,'vmweave-performance-tcp']:
    objects=json.loads(k('get','vm,vmi,pod,pvc,gpurequests.vmweave.io,sharedmemorychannels.vmweave.io,gpuprofiles.vmweave.io','-n',ns,'-o','json'))['items']
    remaining += [o for o in objects if o['metadata']['name'].startswith(('perf-','pilot-','virt-launcher-perf-','virt-launcher-pilot-'))]
for obj in json.loads(k('get','pv','-o','json'))['items']:
    if obj['metadata']['name'].startswith(('perf-','pilot-')):remaining.append(obj)
assert not remaining,[(o['kind'],o['metadata']['name']) for o in remaining]
gpu=call(['nvidia-smi','-i',GPU,'--query-compute-apps=pid,process_name','--format=csv,noheader']).strip()
assert not gpu,('Target GPU still has compute processes',gpu)
node=get('node','gpu-4','default')
assert any(c['type']=='Ready' and c['status']=='True' for c in node['status']['conditions'])
deployments=json.loads(k('get','deployments','-n','vmweave-system','-o','json'))['items']
assert deployments and all(d['status'].get('readyReplicas',0)==d['spec']['replicas'] for d in deployments)
mon=json.loads((BASE/'monitor.json').read_text())
targets=json.load(urllib.request.urlopen(mon['prometheus']+'/api/v1/targets',timeout=10))['data']['activeTargets']
assert len(targets)==3 and all(t['health']=='up' for t in targets)
grafana=json.load(urllib.request.urlopen(mon['grafana']+'/api/health',timeout=10))
assert grafana['database']=='ok'
details={'preserved_resources':preserved,'node':node,'operator_deployments':deployments,'prometheus_targets':targets,'grafana_health':grafana,'target_gpu_processes':gpu}
save(OUT/'final-resource-details.json',details)
save(OUT/'final-audit.json',{
    'utc':datetime.now(timezone.utc).isoformat(),
    'execution_validation':validation['status'],
    'campaign_complete':True,
    'formal_sessions':sum(validation['valid_runs'].values()),
    'measurement_windows':sum(r['windows'] for r in validation['details']),
    'shared_pairs':validation['validated_pairs'],
    'owned_resources_removed':len(cleanup['removed']),
    'owned_workloads_remaining':0,
    'pre_existing_resources_preserved_across_cleanup':len(preserved),
    'target_gpu_idle':True,
    'node_ready':True,
    'operator_ready':True,
    'monitoring_retained':True,
    'prometheus_healthy_targets':len(targets),
    'grafana_database':'ok',
    'enforcement_verdict':'See single/shared analysis; execution PASS does not establish cap compliance.'})
print('Final audit PASS: owned workloads absent; existing resources and monitoring preserved.')
