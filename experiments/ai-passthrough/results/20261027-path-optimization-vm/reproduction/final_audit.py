"""Read-only post-experiment audit; never broad-delete cluster resources."""
import json,hashlib,subprocess,time
from pathlib import Path
import rodinia_campaign as h
O=h.O;C=Path('/home/ubuntu/taeuk/vmweave-path-optimization-20261027')
assert json.loads((O/'post-status.json').read_text())['stage']=='COMPLETE'
prod=json.loads((O/'production-guard.json').read_text());name=prod['name'];ns=prod['namespace']
checks={}
for kind in ['vm','vmi','sharedmemorychannel','gpurequest']:
    old=json.loads((O/('production-before-'+kind+'.json')).read_text())
    new=h.get(kind,name,ns)
    h.save(O/('production-after-'+kind+'.json'),new)
    checks[kind+'_UID_preserved']=new['metadata']['uid']==old['metadata']['uid']
    checks[kind+'_spec_preserved']=new['spec']==old['spec']
c=h.get('sharedmemorychannel',name,ns)
checks['production_ready']=c['status']['phase']=='Ready'
checks['generation_preserved']=c['status']['generation']==prod['generation']
pods=json.loads(h.k('get','pods','-n',ns,'-o','json'))['items']
checks['worker_UID_preserved']=any(p['metadata']['uid']==prod['workerPodUID'] and p['status']['phase']=='Running' for p in pods)
leftovers=[]
for kind in ['vm','vmi','sharedmemorychannel','gpuprofile','gpurequest','pvc','pod']:
    for p in json.loads(h.k('get',kind,'-A','-o','json'))['items']:
        n=p['metadata']['name'];space=p['metadata'].get('namespace','')
        if n.startswith(('path-w-1027-','virt-launcher-path-w-1027-')) or n=='path-native-admin-1027' or space=='path-flyt-1027':leftovers.append([kind,space,n])
for kind in ['pv','namespace']:
    for p in json.loads(h.k('get',kind,'-o','json'))['items']:
        if p['metadata']['name'].startswith(('path-w-1027-','path-flyt-')):leftovers.append([kind,p['metadata']['name']])
checks['owned_cluster_resources_reclaimed']=not leftovers
gpu=subprocess.check_output(['nvidia-smi','-i',h.GPU,'--query-compute-apps=pid','--format=csv,noheader'],text=True).strip()
checks['test_GPU_compute_idle']=not gpu
(O/'gpu-after.csv').write_text(subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.used,utilization.gpu','--format=csv'],text=True))
original=json.loads(Path('/home/ubuntu/taeuk/vmweave-memset-native-20261027/baseline.json').read_text())['sha256']
original_ok={p:hashlib.sha256((h.R/p).read_bytes()).hexdigest()==v for p,v in original.items()}
checks['original_runtime_unchanged']=all(original_ok.values())
candidate=json.loads((O/'candidate-source-manifest.json').read_text())['sha256']
candidate_ok={p:hashlib.sha256((C/p).read_bytes()).hexdigest()==v for p,v in candidate.items()}
checks['candidate_frozen_files_unchanged']=all(candidate_ok.values())
binaries=json.loads((O/'test-binary-sha256.json').read_text())
checks['measurement_binaries_unchanged']=all(hashlib.sha256((h.R/p).read_bytes()).hexdigest()==v for p,v in binaries.items())
for p in (O/'identities').glob('*/cleanup.json'):
    assert json.loads(p.read_text()).get('removed') is True,p
h.save(O/'final-audit.json',{'checks':checks,'leftovers':leftovers,'original_runtime_files':len(original_ok),'candidate_frozen_files':len(candidate_ok),'checked_unix':time.time(),'status':'PASS' if all(checks.values()) else 'FAIL'})
print(json.dumps(checks,indent=2));assert all(checks.values())
