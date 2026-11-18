"""Audit saved provenance after measurement, without rerunning GPU work."""
from pathlib import Path
import json,hashlib
P=Path(__file__).resolve().parents[1]
protocol=json.loads((P/'protocol/frozen.json').read_text())
assert hashlib.sha256((P/'protocol/frozen.json').read_bytes()).hexdigest()==(P/'protocol/frozen.sha256').read_text().split()[0]
for name,expected in protocol['sources'].items():
 assert hashlib.sha256((P.parents[1]/name).read_bytes()).hexdigest()==expected,name
expected_host='266916dac6c5e7e4655526570cf303a6cc017880d2552960abc66017a7c98cf4'
expected_hami='f30f08c8f4bbdada1856231f2ec269d50fc81e08881a4146c9c1bbb3173aebd8'
rows=[];missing=[]
for b in range(1,6):
 for mode in 'NVFL':
  label=f'b{b}-{mode}';s=P/'results'/label;e=P/'evidence'
  execution=json.loads((s/'execution.json').read_text())
  assert execution['status']=='passed'
  order=next(x['condition_order'] for x in protocol['blocks'] if x['block']==b)
  assert execution['order']==order==[x['id'] for x in execution['results']],label
  events=[json.loads(line) for line in (s/'stdout.jsonl').read_text().splitlines() if line.startswith('{')]
  setup=next(x for x in events if x.get('event')=='SETUP')
  assert setup['device_count']==1 and setup['input_seed']==20261117,label
  runtime=json.loads((s/'runtime-libraries.json').read_text())
  hashes={v for p in runtime for v in p['libraries'].values()}
  assert expected_host in hashes and expected_hami in hashes,label
  for suffix in ['-session.json','-released.json','-numa.json','-pod.json','-claim.json']:
   assert (e/(label+suffix)).exists(),label+suffix
  pod=json.loads((e/(label+'-pod.json')).read_text())
  expected_image=protocol['images']['vmweave']['worker'] if mode in 'NV' else protocol['images']['flyt_cell' if mode=='F' else 'lupine_server']
  assert next(c['image'] for c in pod['spec']['containers'] if c['name']=='main')==expected_image,label
  claim=json.loads((e/(label+'-claim.json')).read_text())
  allocations=claim['status']['allocation']['devices']['results']
  assert len(allocations)==1,label
  a=allocations[0]
  assert a['device']=='hami-gpu-1' and a['driver']=='hami-core-gpu.project-hami.io' and a['pool']=='gpu-4',label
  assert a['consumedCapacity']=={'cores':'100','memory':'97887Mi'},label
  if mode!='N':assert (s/'client-path.txt').exists()
  if mode=='V':assert (e/(label+'-layout.bin')).exists()
  f=e/(label+'-client-sha256.txt');count=0
  if f.exists():
   for line in f.read_text().splitlines():
    actual,path=line.split(maxsplit=1)
    key=mode+'/'+Path(path).name
    assert actual==protocol['artifacts'][key],(label,key)
    count+=1
  else:
   assert label=='b1-N',label
   missing.append({'session':label,'item':'supplementary client checksum snapshot','handling':'No retrospective snapshot fabricated. Frozen Native artifact hash was checked before session; actual loaded CUDA/HAMi library hashes are present.'})
  rows.append({'session':label,'native_driver_and_hami_hashes_match':True,'server_image_matches_frozen_digest':True,'gpu1_full_capacity_reserved':True,'client_snapshot_files_checked':count,'numa_snapshot_present':True})
out={'passed':True,'sessions':len(rows),'frozen_protocol_and_source_hashes_match':True,'execution_orders_and_setup_match':True,'checks':rows,'supplementary_missing':missing}
(P/'analysis/metadata-verification.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'passed':True,'sessions':len(rows),'supplementary_missing':missing},indent=2))
