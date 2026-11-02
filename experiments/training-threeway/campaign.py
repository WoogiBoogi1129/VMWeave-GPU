"""Run pilot blocks, freeze the rule-derived protocol, then formal blocks."""
from measure import *
import itertools,random,math
MODES=['passthrough','flyt','vmweave']
orders=list(itertools.permutations(MODES))
random.Random(20261102).shuffle(orders)

def visit(mode,label,cases,phase,stepmap):
 # Flyt assigns a fresh 512MiB SHM region per process without reclaiming offsets.
 # All systems use the same <=5-case visit grouping to stay below its 4GiB BAR.
 for group,offset in enumerate(range(0,len(cases),5),1):
  s=None
  save(B/'progress.json',{'phase':phase,'label':label,'mode':mode,'group':group,'utc':time.time()})
  try:
   s=open_mode(mode,label+'-g'+str(group))
   for case in cases[offset:offset+5]:measure(s,case,phase,label,steps=stepmap[slug(case)],warmup=32)
  finally:
   if s:close_mode(s)
   else:recover_start(mode)

def freeze():
 all_data=[]
 for p in (O/'pilot').glob('*/*/*/result.json'):
  x=json.loads(p.read_text());all_data.append((p.parent.name,x['elapsed_seconds']/x['steps']))
 stepmap={};decision={}
 for case in CASES:
  key=slug(case);values=[v for k,v in all_data if k==key];assert len(values)>=3
  fastest=min(values);slowest=max(values)
  # Shared fixed work, targeting 5s in fastest mode, capped at ~60s in slowest.
  count=max(32,math.ceil(min(5/fastest,60/slowest,4096)/16)*16)
  stepmap[key]=count;decision[key]={'fastest_seconds_per_step':fastest,'slowest_seconds_per_step':slowest,'steps':count,'expected_fast_seconds':count*fastest,'expected_slow_seconds':count*slowest}
 protocol={'created_utc':time.time(),'formal_blocks':10,'orders':[orders[i%6] for i in range(10)],'steps':stepmap,'pilot_rule':decision,'sync':16,'warmup':32,'seed':20261102,'independent_unit':'paired block; mode-specific VMs reused across blocks, fresh VMI per <=5-condition visit, fresh application per condition','time_rule':'target 5s fastest subject to ~60s slowest and 4096-step cap; 32 minimum, multiples of16; disclose short fastest intervals','app_environment':APPENV}
 assert not (O/'protocol.json').exists();save(O/'protocol.json',protocol);return protocol

if __name__=='__main__':
 assert json.loads((O/'correctness/summary.json').read_text())['all_passed']
 if not (O/'protocol.json').exists():
  save(O/'pilot-plan.json',{'orders':orders[:5],'first_block':'all 10 conditions','other_blocks':['small-32-resident','large-1024-h2d'],'steps':32,'warmup':32,'formal_step_rule':'min(5/fastest_step,60/slowest_step,4096), rounded up to16, minimum32','formal_blocks':10})
  for i in range(5):
   cases=CASES if i==0 else [('small',32,'resident'),('large',1024,'h2d')]
   for mode in orders[i]:visit(mode,'p'+str(i+1),cases,'pilot',{slug(c):32 for c in cases})
  protocol=freeze()
 else:protocol=json.loads((O/'protocol.json').read_text())
 for i,order in enumerate(protocol['orders']):
  cases=CASES[i:]+CASES[:i]
  for mode in order:visit(mode,'b'+str(i+1),cases,'formal',protocol['steps'])
 save(O/'measurements-complete.json',{'formal_runs':300,'pilot_runs':54,'utc':time.time()})
 print('MEASUREMENTS_COMPLETE',flush=True)
