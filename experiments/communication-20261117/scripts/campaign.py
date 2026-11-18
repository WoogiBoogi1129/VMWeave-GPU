from run_session import *
from cleanup import stop_active,verify

def check_hashes(protocol):
 for name,expected in protocol['sources'].items():assert hashlib.sha256((R/name).read_bytes()).hexdigest()==expected,name
 for name,expected in protocol['artifacts'].items():assert hashlib.sha256((B/'artifacts'/name).read_bytes()).hexdigest()==expected,name

def campaign():
 protocol_path=O/'protocol/frozen.json'
 assert hashlib.sha256(protocol_path.read_bytes()).hexdigest()==(O/'protocol/frozen.sha256').read_text().split()[0]
 protocol=json.loads(protocol_path.read_text());check_hashes(protocol)
 try:
  for block in protocol['blocks']:
   for mode in block['backend_order']:
    label=f"b{block['block']}-{mode}"
    check_hashes(protocol)
    if (O/'results'/label/'execution.json').exists():
     e=json.loads((O/'results'/label/'execution.json').read_text())
     assert e['status']=='passed' and len(e['results'])==16,'Never overwrite failed/partial session'
     assert (O/'evidence'/(label+'-released.json')).exists()
     continue
    print('SESSION_START',label,time.time(),flush=True)
    run(mode,label,block['condition_order'])
    print('SESSION_COMPLETE',label,time.time(),flush=True)
   print('BLOCK_COMPLETE',block['block'],time.time(),flush=True)
   snapshot=verify()
   preservation=O/'evidence'/f"block-{block['block']}-preservation.json"
   if not preservation.exists():save(preservation,snapshot)
   assert not snapshot['configuration_changes'],'Independent config change; inspect before continuing'
  save(O/'evidence/campaign-complete.json',{'utc':time.time(),'sessions':20,'intervals':320})
  print('CAMPAIGN_COMPLETE',flush=True)
 finally:stop_active()
if __name__=='__main__':campaign()
