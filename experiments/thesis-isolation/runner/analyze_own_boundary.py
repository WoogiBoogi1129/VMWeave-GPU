"""Join own-control commands, endpoint requests, and Worker CUDA context records."""
import argparse,json
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('run',type=Path);args=parser.parse_args()
out=args.run;root=out.parent/'runs';result=json.loads((out/'result.json').read_text());joined=[]
for name in result['sessions']:
 d=root/name;commands={};requests={};active=None
 for line in (d/'probe-stderr.txt').read_text().splitlines():
  if line.startswith('BOUNDARY_COMMAND '):
   marker=json.loads(line.split(' ',1)[1]);active=marker if marker['stage']=='begin' else None
  if line.startswith('FLYT_TRACE '):
   r=json.loads(line.split(' ',1)[1]);key=(r['allocation'],r['generation'],r['session_id'],r['request_id'])
   rows=requests.setdefault(key,{});assert r['event'] not in rows;rows[r['event']]=r
   if active:commands[key]={'sequence':active['sequence'],'op':active['op']}
 active=None;contexts={};worker={}
 for line in (d/'worker-trace.txt').read_text().splitlines():
  if line.startswith('FLYT_TRACE '):
   r=json.loads(line.split(' ',1)[1]);key=(r['allocation'],r['generation'],r['session_id'],r['request_id']);rows=worker.setdefault(key,{})
   assert r['event'] not in rows;rows[r['event']]=r;active=key if r['event']=='take' else None
  elif line.startswith('BOUNDARY_CONTEXT '):
   assert active and worker[active]['take']['api_id']==0x2033
   assert active not in contexts;contexts[active]=json.loads(line.split(' ',1)[1])
 assert requests.keys()==worker.keys()
 for key,g in requests.items():
  w=worker[key];assert set(g)=={'submit','receive'} and set(w)=={'take','respond'}
  assert g['submit']['monotonic_ns']<=g['receive']['monotonic_ns']
  assert w['take']['monotonic_ns']<=w['respond']['monotonic_ns']
  assert len({x['api_id'] for x in [*g.values(),*w.values()]})==1
  for field in ['transport_status','result_domain','api_result','output_bytes']:assert g['receive'][field]==w['respond'][field]
  if g['submit']['api_id']==0x2033:assert key in contexts
  joined.append({'vm':name,'allocation':key[0],'generation':key[1],'session_id':key[2],'request_id':key[3],
   'api_id':g['submit']['api_id'],'command':commands.get(key),'worker_pid':w['take']['pid'],'cuda_context':contexts.get(key),
   'transport_status':w['respond']['transport_status'],'api_result':w['respond']['api_result']})
 for seq in {x['sequence'] for x in commands.values() if x['op'] in ['read','write']}:
  rows=[r for r in joined if r['vm']==name and r['command'] and r['command']['sequence']==seq]
  apis=[r['api_id'] for r in rows];assert apis.count(0x2033)==1 and apis.count(0x1020)==1
  assert apis.index(0x2033)<apis.index(0x1020)
  assert all(r['api_result']==0 and r['transport_status']==0 for r in rows)
(out/'joined-requests.json').write_text(json.dumps(joined,indent=2)+'\n')
print(json.dumps({'matched_requests':len(joined),'kernel_requests':sum(r['api_id']==0x2033 for r in joined),'sync_requests':sum(r['api_id']==0x1020 for r in joined),'sessions':len(result['sessions'])}))
