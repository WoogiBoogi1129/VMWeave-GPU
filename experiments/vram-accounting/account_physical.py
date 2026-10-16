"""Reconcile stable full-allocation plateaus without assuming physical == quota."""
import json,lzma,collections
from pathlib import Path
P=Path(__file__).resolve().parent;E=P/'evidence/20261016';B=P.parents[1]/'.local/vram-accounting-20261016'
groups=collections.defaultdict(list)
expected_pids={}
for d in (P/'results/20261016/runs').iterdir():
 matches=list(d.glob('*worker-affinity.json'))
 if matches:expected_pids[d.name]={int(x['pid']) for x in json.loads(matches[0].read_text())['processes']}
source=E/'monitoring/observations.jsonl.xz'
f=lzma.open(source,'rt') if source.exists() else (B/'monitor.jsonl').open()
for line in f:
 r=json.loads(line)
 if 'gpu_mib' not in r:continue
 vals=[(n,s) for n,s in r['state'].items() if n.startswith(('vram-single-','vram-pair-v3-')) and s.get('total',0)>0 and s.get('live_requested',0)>0 and s.get('free')==0 and r['utc']-s.get('host_utc',r['utc'])>=.8]
 if not vals:continue
 try:ps=[int(x.split(',')[1].strip()) for x in r['processes'].splitlines() if x.strip()]
 except ValueError:continue
 # Require all observed physical processes to have corresponding full-allocation state.
 if len(vals)!=len(ps):continue
 actual_pids={int(x.split(',')[0]) for x in r['processes'].splitlines() if x.strip()}
 allowed=set().union(*(expected_pids.get(n,set()) for n,_ in vals))
 if actual_pids!=allowed:continue
 key='single-'+str(vals[0][1]['total']//1048576) if len(vals)==1 else 'pair'
 groups[key].append({'utc':r['utc'],'runs':[n for n,s in vals],'quota_sum_mib':sum(s['total'] for n,s in vals)/1048576,'device_mib':r['gpu_mib'],'process_sum_mib':sum(ps),'residual_mib':r['gpu_mib']-sum(ps)})
f.close();out={'selection':'At least 0.8s after full allocation event, free=0, all active target GPU PIDs matched to the recorded Worker affinity evidence for full-state runs; no equality filter on memory values. CLI samples are not atomic.','groups':{}}
for k,rows in groups.items():
 out['groups'][k]={'samples':len(rows),'device_mib_range':[min(x['device_mib'] for x in rows),max(x['device_mib'] for x in rows)],'process_mib_range':[min(x['process_sum_mib'] for x in rows),max(x['process_sum_mib'] for x in rows)],'residual_mib_range':[min(x['residual_mib'] for x in rows),max(x['residual_mib'] for x in rows)],'observations':rows}
(E/'physical-reconciliation.json').write_text(json.dumps(out,indent=2)+'\n')
print({k:{a:b for a,b in v.items() if a!='observations'} for k,v in out['groups'].items()})
