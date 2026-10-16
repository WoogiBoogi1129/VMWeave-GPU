"""Offline evidence audit; never executes CUDA or changes cluster resources."""
import json,csv,math,re,hashlib,argparse
from pathlib import Path
P=Path(__file__).resolve().parent;R=P/'results/20261016';E=P/'evidence/20261016';E.mkdir(parents=True,exist_ok=True)
parser=argparse.ArgumentParser();parser.add_argument('--final',action='store_true');a=parser.parse_args()
singles=[];pairs=[];torch=[];ledger=[];files=set()
def read(p):files.add(p);return json.loads(p.read_text())
for d in sorted((R/'runs').glob('vram-single-*')):
 if not (d/'summary.json').exists() or not (d/'cleanup.json').exists():continue
 s=read(d/'summary.json');assert s['status']=='PASS';identity=read(d/'identity.json');affinity=read(next(d.glob('*worker-affinity.json')));assert affinity['pod_uid']==identity['worker_uid'];expected_pids={x['pid'] for x in affinity['processes']};c=read(d/'cleanup.json');assert c['released'];channel=read(d/'channel-released.json');assert channel['status']['phase']=='Released' and channel['status']['memoryMiB']==s['quota_mib']
 ev=d/'events.jsonl';files.add(ev);events=[json.loads(l) for l in ev.read_text().splitlines()];base=events[0]['total']-events[0]['free'];slots=[];max_residual=0
 for r in events:
  assert r['info_rc']==0 and r['verify_rc']==0 and r['total']==s['quota_mib']*1048576
  if r['op']=='alloc':
   added=r['count']-len(slots)
   assert added>=0
   slots.extend([r['bytes']]*added)
  elif r['op']=='clear' and r['rc']==0:slots=[]
  elif r['op']=='free' and r['rc']==0:slots[r['bytes']]=0
  requested=sum(slots);rounded=sum((n+4095)//4096*4096 for n in slots)
  assert requested==r['live_requested'],(d.name,r,slots)
  residual=r['total']-r['free']-base-rounded;max_residual=max(max_residual,abs(residual))
  ledger.append({'run':d.name,'label':r['label'],'utc':r['host_utc'],'requested':requested,'rounded_derived':rounded,'guest_used':r['total']-r['free'],'baseline':base,'residual':residual,'rc':r['rc']})
 assert max_residual<=4096,(d,max_residual)
 for k in ['cold','warm']:assert s[k]['min_failure']-s[k]['max_success']==4096
 acct=d/'accounting.jsonl';files.add(acct);observations=[json.loads(l) for l in acct.read_text().splitlines()]
 accounting=[]
 for o in observations:
  if not o['hami']:raise ValueError('missing HAMi '+d.name)
  h=float(o['hami'].split()[-1]);ps=[line for line in o['gpu_processes'].splitlines() if line.strip()];assert len(ps)==1,(d,ps)
  assert int(ps[0].split(',')[0]) in expected_pids
  pm=int(ps[0].split(',')[1].strip().split()[0])*1048576
  accounting.append({'label':o['label'],'hami_bytes':h,'nvml_process_bytes':pm,'difference':pm-h})
 assert all(abs(x['difference'])<=2097152 for x in accounting)
 singles.append({'run':d.name,'quota_mib':s['quota_mib'],'baseline_bytes':base,'cold_max':s['cold']['max_success'],'warm_max':s['warm']['max_success'],'min_failure':s['warm']['min_failure'],'available_pct':s['warm']['max_success']/s['warm']['quota']*100,'ledger_max_abs_residual':max_residual,'accounting':accounting})
for d in sorted((R/'pairs').glob('*')):
 if not (d/'summary.json').exists():continue
 s=read(d/'summary.json');assert s['status']=='PASS'
 if not all((R/'runs'/n/'cleanup.json').exists() for n in s['sessions']):continue
 pair_accounting=[]
 for n in s['sessions']:
  z=R/'runs'/n;assert read(z/'cleanup.json')['released'];read(z/'channel-released.json');files.update([z/'events.jsonl',z/'accounting.jsonl',z/'stderr.txt']);control=json.loads((z/'events.jsonl').read_text().splitlines()[0]);assert control['op']=='selftest' and control['rc']==0 and control['middle']==-12 and control['tail']==-13 and control['head']==-11
  ident=read(z/'identity.json');aff=read(next(z.glob('*worker-affinity.json')));assert aff['pod_uid']==ident['worker_uid'];pids={x['pid'] for x in aff['processes']}
  for line in (z/'accounting.jsonl').read_text().splitlines():
   o=json.loads(line);h=float(o['hami'].split()[-1]);matched=[v for v in o['gpu_processes'].splitlines() if int(v.split(',')[0]) in pids];assert len(matched)==1;pm=int(matched[0].split(',')[1].strip().split()[0])*1048576;assert abs(pm-h)<=2097152;pair_accounting.append({'run':n,'label':o['label'],'hami_bytes':h,'nvml_process_bytes':pm})
  trace=[json.loads(line.removeprefix('FLYT_TRACE ')) for line in (z/'stderr.txt').read_text().splitlines() if line.startswith('FLYT_TRACE ')]
  returns=[t for t in trace if t.get('requested_bytes') and t.get('api_result') is not None];assert any(t['requested_bytes']==4096 and t['api_result']==0 for t in returns);assert any(t['requested_bytes']==8192 and t['api_result']==0 for t in returns);assert any(t['api_result']==2 and t['transport_status']==0 for t in returns)
 pairs.append({'run':d.name,**s,'accounting':pair_accounting})
for d in sorted((R/'runs').glob('vram-torch-*')):
 if not (d/'summary.json').exists() or not (d/'cleanup.json').exists():continue
 s=read(d/'summary.json');assert s['status']=='PASS' and read(d/'cleanup.json')['released'];read(d/'channel-released.json');files.update([d/'torch-events.jsonl',d/'accounting.jsonl'])
 ident=read(d/'identity.json');aff=read(next(d.glob('*worker-affinity.json')));assert aff['pod_uid']==ident['worker_uid'];pids={x['pid'] for x in aff['processes']}
 acct=[json.loads(l) for l in (d/'accounting.jsonl').read_text().splitlines()];obs={x['label']:x for x in acct}
 rows=[]
 for row in s['stages']:
  if row['stage']=='done':continue
  o=obs[row['stage']];h=float(o['hami'].split()[-1]);ps=o['gpu_processes'].splitlines();assert len(ps)==1
  assert int(ps[0].split(',')[0]) in pids
  pm=int(ps[0].split(',')[1].strip().split()[0])*1048576
  assert 0<=row['allocated']<=row['reserved']
  assert h==row['total']-row['free']
  rows.append({**row,'hami_bytes':h,'nvml_process_bytes':pm,'non_allocator_hami_bytes':h-row['reserved'],'nvml_minus_hami_bytes':pm-h,'hami_nvml_within_2mib':abs(pm-h)<=2097152})
 assert [r['stage'] for r in rows]==['torch-context','model-data','first-training-step','training-complete','tensors-deleted','empty-cache']
 trained=rows[3];assert trained['steps']==20 and math.isfinite(trained['final_loss']) and trained['final_loss']<trained['initial_loss']
 assert all(r['total']==s['quota_mib']*1048576 for r in rows)
 torch.append({'run':d.name,'quota_mib':s['quota_mib'],'stages':rows})
supplement=[]
for d in sorted((R/'runs').glob('vram-mlp-boundary-*')):
 if not (d/'summary.json').exists() or not (d/'cleanup.json').exists():continue
 data=read(d/'summary.json');assert data['status']=='PASS' and read(d/'cleanup.json')['released'];read(d/'channel-released.json')
 ident=read(d/'identity.json');aff=read(next(d.glob('*worker-affinity.json')));assert aff['pod_uid']==ident['worker_uid'];pids={x['pid'] for x in aff['processes']}
 files.update([d/'torch-events.jsonl',d/'accounting.jsonl'])
 obs={x['label']:x for x in map(json.loads,(d/'accounting.jsonl').read_text().splitlines())};rows=[]
 for row in data['stages']:
  if row['stage']=='done':continue
  o=obs[row['stage']];h=float(o['hami'].split()[-1]);ps=o['gpu_processes'].splitlines();assert len(ps)==1 and int(ps[0].split(',')[0]) in pids
  pm=int(ps[0].split(',')[1].strip().split()[0])*1048576;assert h==row['total']-row['free']
  rows.append({**row,'hami_bytes':h,'nvml_process_bytes':pm,'nvml_minus_hami_bytes':pm-h,'hami_nvml_within_2mib':abs(pm-h)<=2097152})
 stages={r['stage']:r for r in rows};maximum=stages['trained-max'];failure=stages['trained-min-fail']
 assert 0<=maximum['free']<4096 and maximum['api_rc']==0 and maximum['sampled_bytes']==48
 assert maximum['direct_requested']==failure['reported_free_before']//4096*4096
 assert failure['api_rc']==2 and failure['direct_requested']==maximum['direct_requested']+4096
 assert stages['trained-extra-oom']['api_rc']==2 and stages['trained-extra-oom']['extra_requested']==4096
 assert stages['trained-direct-free']['free']==stages['training-complete']['free']
 assert math.isfinite(stages['trained-recovery']['loss'])
 supplement.append({'run':d.name,'quota_mib':data['quota_mib'],'stages':rows,'logical_boundary_enforced':True,'physical_process_limit_exceeded':maximum['nvml_process_bytes']>data['quota_mib']*1048576})
summary={'single_count':len(singles),'pair_count':len(pairs),'torch_count':len(torch),'final':a.final,'singles':singles,'pairs':pairs,'torch':torch,'supplementary_trained_boundary':supplement}
if a.final:assert len(supplement)==2,len(supplement)
if a.final:assert (len(singles),len(pairs),len(torch))==(10,10,10),(len(singles),len(pairs),len(torch))
(E/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
for name,rows in [('boundaries', [{k:v for k,v in r.items() if k!='accounting'} for r in singles]),('ledger',ledger),('torch-stages',[{'run':r['run'],'quota_mib':r['quota_mib'],**s} for r in torch for s in r['stages']])]:
 if rows:
  keys=list(dict.fromkeys(k for r in rows for k in r));f=(E/(name+'.csv')).open('w');w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows);f.close()
(E/'raw-sha256.json').write_text(json.dumps({str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(files)},indent=2)+'\n')
print('AUDIT',len(singles),'single',len(pairs),'pairs',len(torch),'torch;',len(supplement),'supplementary; raw evidence consistency checks passed; accounting mismatches retained')
