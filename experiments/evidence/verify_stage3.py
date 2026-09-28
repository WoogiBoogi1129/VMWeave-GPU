"""Offline assertions over original logs, observed phase overlap, output bytes and cleanup."""
import argparse,collections,csv,gzip,hashlib,json,struct
from pathlib import Path
from verify_stage2 import parse
MIB=1048576

def verify_pair(directory):
 d=Path(directory).resolve();read=lambda p:json.loads(p.read_text());results={};bindings={};all_receipts={}
 for role,limit in [('A',1024),('B',4096)]:
  r=d/role;rows=[json.loads(s) for s in (r/'stdout.jsonl').read_text().splitlines()]
  receipts=[json.loads(s) for s in (r/'host-receipts.jsonl').read_text().splitlines()];assert [x['record'] for x in receipts]==rows
  all_receipts[role]=receipts
  assert len({x['pid'] for x in rows})==1 and all(x['vm']==role for x in rows)
  assert all(a['monotonic_seconds']<=b['monotonic_seconds'] for a,b in zip(rows,rows[1:]))
  alloc=[x for x in rows if x['event']=='ALLOC'];large=next(x for x in alloc if x['phase']=='large')
  assert large['requested_bytes']==1536*MIB
  assert large['api_result']==(2 if role=='A' else 0)
  assert large['live_allocated_bytes']==(0 if role=='A' else 1536*MIB)
  if role=='A':
   small=next(x for x in alloc if x['phase']=='small');assert small['requested_bytes']==128*MIB and small['api_result']==0 and small['live_allocated_bytes']==128*MIB
   assert rows.index(large)<rows.index(small)
  assert len(alloc)==(3 if role=='A' else 2)
  progress=[x for x in rows if x['event']=='PROGRESS'];assert len(progress)>2
  assert [x['completed'] for x in progress]==list(range(1,len(progress)+1))
  assert all(x['checked_elements']==524288 and x['mismatches']==0 for x in progress)
  result=rows[-1];assert result['event']=='RESULT' and result['status']=='PASS' and result['mismatches']==0 and result['live_allocated_bytes']==0
  assert result['completed']==len(progress) and result['checked_elements_total']==len(progress)*524288
  seed=rows[0]['seed'];hashes={}
  for part in ['head','tail']:
   data=gzip.decompress((r/('stage3-output-'+part+'.bin.gz')).read_bytes())
   ref=struct.pack('<262144I',*((seed+i+len(progress)-1+19 if part=='head' else (seed+i)^0xa5a5a5a5) for i in range(262144)))
   assert data==ref,'independent byte comparison '+role+' '+part;hashes[part]=hashlib.sha256(data).hexdigest()
  free=next(x for x in rows if x['event']=='FREE' and x['phase']=='final')
  assert free['freed_bytes']==(128 if role=='A' else 1536)*MIB and free['api_result']==0
  binding=read(r/'trace-binding.json');bindings[role]=binding
  endpoints=parse((r/'guest-stderr.txt').read_text())+parse((r/'worker-stderr.txt').read_text());groups=collections.defaultdict(list)
  for x in endpoints:
   assert tuple(x[k] for k in ['allocation','generation','session_id'])==tuple(binding[k] for k in ['allocation','generation','session_id'])
   groups[x['request_id']].append(x)
  assert sorted(groups)==list(range(1,len(groups)+1));oom=0;mallocs=[]
  for rid,records in sorted(groups.items()):
   assert collections.Counter((x['role'],x['event']) for x in records)==collections.Counter([('guest','submit'),('worker','take'),('worker','respond'),('guest','receive')])
   assert len({(x['api_id'],x['input_bytes']) for x in records})==1
   replies=[x for x in records if x['event'] in ['respond','receive']]
   assert all(x['transport_status']==0 for x in replies)
   assert all(replies[0][key]==replies[1][key] for key in ['api_result','result_domain','output_bytes'])
   response=replies[0]
   expected=2 if role=='A' and response['api_id']==4112 and response.get('requested_bytes')==1536*MIB else 0
   assert response['api_result']==expected
   if expected:oom+=1
   if response['api_id']==4112:mallocs.append({'request_id':rid,'requested_bytes':response['requested_bytes'],'api_result':response['api_result'],'allocation_handle':response.get('allocation_handle')})
  assert oom==(1 if role=='A' else 0)
  assert [(x['requested_bytes'],x['api_result']) for x in mallocs]==[(x['requested_bytes'],x['api_result']) for x in alloc]
  applied=read(r/'applied.json');assert applied['profile']['spec']['memoryMiB']==limit and applied['channel']['status']['memoryMiB']==limit
  assert str(applied['worker']['spec']['containers'][0]['resources']['limits']['nvidia.com/gpumem'])==str(limit)
  assert applied['request']['spec']['memory']==str(limit)+'Mi'
  assert read(r/'process.json')['exit_code']==0 and read(r/'cleanup.json')['released']
  assert read(r/'released-channel.json')['status']['phase']=='Released'
  results[role]={'status':'PASS','memory_limit_mib':limit,'large_api_result':large['api_result'],'expected_oom_count':oom,'same_guest_pid':rows[0]['pid'],'matched_requests':len(groups),'trace_records':len(endpoints),'completed_checks':len(progress),'checked_elements_total':result['checked_elements_total'],'mismatches':0,'output_sha256':hashes,'malloc_requests':mallocs}
 assert bindings['A']['gpu_uuid']==bindings['B']['gpu_uuid']
 identities={role:read(d/role/'identity.json') for role in ['A','B']}
 assert identities['A']['worker_uid']!=identities['B']['worker_uid'] and identities['A']['vmi_uid']!=identities['B']['vmi_uid']
 with (d/'gpu-processes.csv').open() as f:gpu=list(csv.DictReader(f,skipinitialspace=True))
 for role in ['A','B']:
  runtime=read(d/role/'runtime-libraries.json');assert len(runtime)==1
  assert any(int(x['pid'])==runtime[0]['pid'] and x['gpu_uuid']==bindings[role]['gpu_uuid'] for x in gpu)
  assert any('libvgpu.so' in path for path in runtime[0]['library_hashes'])
  assert runtime[0]['environment']['CUDA_DEVICE_MEMORY_LIMIT_0']==('1024m' if role=='A' else '4096m')
 assert all(bindings['A'][k]!=bindings['B'][k] for k in ['allocation','generation','session_id'])
 a=all_receipts['A'];b=all_receipts['B']
 oom=next(x['host_received_utc'] for x in a if x['record']['event']=='ALLOC' and x['record']['phase']=='large')
 small=next(x['host_received_utc'] for x in a if x['record']['event']=='ALLOC' and x['record']['phase']=='small')
 free=next(x['host_received_utc'] for x in a if x['record']['event']=='FREE' and x['record']['phase']=='final')
 ongoing=[x for x in b if x['record']['event']=='PROGRESS' and x['record']['live_allocated_bytes']==1536*MIB]
 intervals={'before_A_OOM':[x for x in ongoing if x['host_received_utc']<oom], 'after_OOM_before_small':[x for x in ongoing if oom<x['host_received_utc']<small], 'during_A_small':[x for x in ongoing if small<x['host_received_utc']<free], 'after_A_free':[x for x in ongoing if free<x['host_received_utc']]}
 assert all(intervals.values()),'B must complete verified work on both sides of A events'
 assert len({x['record']['guest_pointer'] for x in ongoing})==1
 return {'status':'PASS','pair':d.name,'gpu_uuid':bindings['A']['gpu_uuid'],'roles':results,'B_checks_by_host_receipt_interval':{k:len(v) for k,v in intervals.items()},'B_same_live_allocation':True,'clock_basis':'Host log receipt intervals; not cross-VM one-way latency','full_large_allocation_checked':False,'checked_sample':'First and last 1 MiB per completed check'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args();print(json.dumps(verify_pair(a.directory),indent=2))
