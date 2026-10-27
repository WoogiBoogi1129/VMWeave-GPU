import json,statistics
from pathlib import Path
O=Path('experiments/ai-passthrough/results/20261027-path-optimization-vm')
conditions={};resources={}
for spin in [0,10,50]:
    d=O/'qualification'/('qual-spin'+str(spin))/'candidate'
    q=json.loads((d/'micro.json').read_text());assert q['status']=='PASS'
    conditions[spin]={(r['operation'],r['bytes']):r for r in q['rows']}
    resources[spin]=json.loads((d/'resource-accounting.json').read_text())['summary']
rows=[]
for op,n in sorted(conditions[0]):
    row={'operation':op,'bytes':n,'profiles':{}}
    for spin in [0,10,50]:
        r=conditions[spin][op,n];assert r['correct']
        row['profiles'][str(spin)]={k.replace('_ns','_ms'):statistics.median(s[k] for s in r['samples'] if not s['warmup'])/1e6 for k in ['api_ns','completion_ns','caller_cpu_ns']}
    rows.append(row)
result={'status':'EXPLORATORY_ONLY','independent_VMs_per_profile':1,'order_us':[0,50,10],'sleep_us':50,'units':'milliseconds','rows':rows,'whole_probe_resource_accounting':resources,'limitations':['One VM per profile; five in-process samples are not independent VM replications','All checks and setup remain outside formal timing campaign','Worker memory peak covers its qualification lifetime, not microbenchmark only','No automatic change of defaults or production settings']}
(O/'wait-profile-comparison.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(resources,indent=2))
