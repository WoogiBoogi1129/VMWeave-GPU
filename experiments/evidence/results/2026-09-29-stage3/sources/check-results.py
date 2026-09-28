import collections,csv,gzip,hashlib,json,statistics,sys,subprocess,tempfile,shutil
from pathlib import Path
sys.path.insert(0,'experiments/evidence')
from verify_stage3 import verify_pair
root=Path('experiments/evidence/results/2026-09-29-stage3')
results=[verify_pair(root/('pair-'+str(i))) for i in range(1,4)]
identities=[json.loads((root/('pair-'+str(i))/role/'identity.json').read_text()) for i in range(1,4) for role in ['A','B']]
for key in ['allocation','vmi_uid','worker_uid','channel_uid']:assert len({x[key] for x in identities})==6
observations=[json.loads(s) for s in gzip.decompress((root/'monitoring/observations.jsonl.gz').read_bytes()).decode().splitlines()]
quality={}
for n in range(1,4):
 pair='pair-'+str(n);w=json.loads((root/pair/'plot-window.json').read_text());obs=[x for x in observations if w['start']<=x['host_utc']<=w['end']]
 gaps=[b['host_utc']-a['host_utc'] for a,b in zip(obs,obs[1:])]
 quality[pair]={'raw_samples':len(obs),'sample_interval_mean_seconds':statistics.mean(gaps),'sample_interval_max_seconds':max(gaps),'collector_error_samples':sum(bool(x['errors']) for x in obs)}
 assert quality[pair]['collector_error_samples']==0 and max(gaps)<2
 for metric in ['s3_live_bytes','s3_limit_bytes','s3_hami_memory_bytes','s3_completed_checks_total','s3_mismatches_total','s3_oom_total']:
  data=json.loads((root/'monitoring'/(pair+'-'+metric+'.json')).read_text())['data']['result']
  assert {x['metric']['vm'] for x in data}=={'A','B'}
  for series in data:
   values=[float(v) for _,v in series['values']]
   if metric=='s3_live_bytes':assert max(values)==(128 if series['metric']['vm']=='A' else 1536)*1048576
   if metric=='s3_mismatches_total':assert set(values)=={0}
   if metric=='s3_oom_total':assert max(values)==(1 if series['metric']['vm']=='A' else 0)
   if metric=='s3_hami_memory_bytes':assert max(values)>0
 up=json.loads((root/'monitoring'/(pair+'-up.json')).read_text())['data']['result'];assert all(float(v)==1 for s in up for _,v in s['values'])
# Deliberately corrupt copies to verify that expected-OOM and byte-integrity failures are rejected.
negative=[]
for case in ['unexpected_success','wrong_output_byte']:
 with tempfile.TemporaryDirectory(dir='.local/stage3-20260929') as tmp:
  dest=Path(tmp)/'pair-1';shutil.copytree(root/'pair-1',dest)
  if case=='unexpected_success':
   p=dest/'A/stdout.jsonl';rows=[json.loads(s) for s in p.read_text().splitlines()]
   for r in rows:
    if r['event']=='ALLOC' and r['phase']=='large':r['api_result']=0
   p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
   p=dest/'A/host-receipts.jsonl';receipts=[json.loads(s) for s in p.read_text().splitlines()]
   for x,r in zip(receipts,rows):x['record']=r
   p.write_text(''.join(json.dumps(r)+'\n' for r in receipts))
  else:
   p=dest/'B/stage3-output-tail.bin.gz';data=bytearray(gzip.decompress(p.read_bytes()));data[0]^=1;p.write_bytes(gzip.compress(data,mtime=0))
  try:verify_pair(dest)
  except AssertionError:negative.append(case)
  else:raise AssertionError('Corruption was not rejected')
report={'status':'PASS','independent_pairs':3,'unique_vmis_workers_allocations':6,'expected_oom_count':3,'all_pair_checks_pass':True,'negative_checks_rejected':negative,'monitoring_quality':quality}
(root/'bundle-check.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
