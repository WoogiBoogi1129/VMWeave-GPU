"""Audit four native CUDA peer pilots from raw event streams and ownership records."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('campaign',type=Path);root=p.parse_args().campaign
conditions=json.loads((root/'conditions.json').read_text());assert {(x['direction'],x['operation']) for x in conditions}=={(d,o) for d in ['ab','ba'] for o in ['read','write']}
summary=[];uids=set();host_pids=set();total_checks=0;total_own_kernels=0
for condition in conditions:
 assert condition['returncode']==0
 # Resolve locally by directory name so extracted evidence is independently auditable.
 d=root.parent/Path(condition['path']).name
 binding=json.loads((d/'target-binding.json').read_text());ownership=json.loads((d/'ownership.json').read_text());result=json.loads((d/'result.json').read_text())
 byname={x['process']:x for x in ownership};requester=byname[binding['requester']];owner=byname[binding['owner']]
 assert requester['host']['host_pid']!=owner['host']['host_pid']
 assert requester['ready']['gpu']==owner['ready']['gpu']=='GPU-7d708c42-8d4a-16d5-0746-474567157aa3'
 assert binding['owner_ready']==owner['ready'] and binding['requester_ready']==requester['ready']
 assert owner['ready']['mapping_base']==owner['ready']['address'] and owner['ready']['mapping_bytes']==4096
 assert binding['access_bytes']==4 and binding['owner_expected_first']==owner['ready']['seed']^0x5a5a5a5a
 rows={}
 for record in ownership:
  assert record['pod_uid'] not in uids;uids.add(record['pod_uid']);host_pids.add(record['host']['host_pid'])
  folder=root.parent/'runs'/record['process']
  stream=[json.loads(x) for x in (folder/'requests-events.jsonl').read_text().splitlines()]
  assert stream[0]['event']=='ready' and stream[0]['address']==record['ready']['address']
  assert json.loads((folder/'cleanup.json').read_text())['released']
  launches={}
  for event in stream:
   if event['event']=='launch_begin':
    assert event['sequence'] not in launches
    assert event['context_query']==0 and event['context']==record['ready']['context'];launches[event['sequence']]=event
   elif event['event']=='access':
    assert event['sequence'] in launches and launches[event['sequence']]['own_buffer']
    assert all(event[k]==0 for k in ['prep','launch','sync','copy']) and event['observed']==event['expected'];total_own_kernels+=1
   elif event['event']=='check':
    assert event['code']==0 and event['mismatches']==0;total_checks+=1
  rows[record['process']]=stream
 req=rows[binding['requester']];peer=[x for x in req if x['event']=='peer_access'];assert len(peer)==1
 access=peer[0];sequence=access['sequence'];begin=next(x for x in req if x['event']=='launch_begin' and x['sequence']==sequence)
 submitted=next(x for x in req if x['event']=='launch_result' and x['sequence']==sequence)
 assert not begin['own_buffer'] and begin['access_bytes']==4 and begin['mapping']==500
 assert begin['target']==access['target']==owner['ready']['address']
 assert access['op']=='peer_'+condition['operation'] and access['prep']==0
 assert submitted['code']==access['launch']==0 and access['sync']==700 and access['copy']==-1 and not access['read_valid']
 assert req.index(begin)<req.index(submitted)<req.index(access)
 owner_stream=rows[binding['owner']]
 post=[x for x in owner_stream if x['received_host_utc']>access['received_host_utc']]
 assert len([x for x in post if x['event']=='check'])==2
 assert len([x for x in post if x['event']=='access' and x['op']=='read'])==1
 assert result['observations']['access']==access and result['observations']['owner_buffer_intact']
 state=json.loads((d/'status.json').read_text());assert state['state']=='CLOSED' and state['failure'] is None and not state['cleanup_errors']
 summary.append({'direction':condition['direction'],'operation':condition['operation'],'run':d.name,'target':access['target'],
  'launch':access['launch'],'sync':access['sync'],'read_result_valid':access['read_valid'],'owner_buffer_intact':True,'owner_post_kernel_success':True,'closed':True})
assert len(uids)==8 and total_checks==72 and total_own_kernels==28,(len(uids),total_checks,total_own_kernels)
analysis={'status':'VERIFIED_NATIVE_PEER_PILOT','conditions':summary,'peer_kernels_submitted':4,'synchronization_error_700':4,
 'own_control_and_post_kernels':total_own_kernels,'buffer_checks':total_checks,'buffer_mismatches':0,'unique_pods':len(uids),'host_processes':len(host_pids),
 'scope':'Four one-shot native CUDA/HAMi synthetic-address cases; not VMWeave end-to-end or universal GPU isolation proof.','cleanup_verified':True}
(root/'analysis.json').write_text(json.dumps(analysis,indent=2)+'\n');print(json.dumps(analysis))
