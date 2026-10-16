"""Run five paired blocks, only after the preregistered correctness gate."""
import json,time
from campaign import c,s,BASE,OUT,VM,CONDITIONS,measure
from passthrough_guest import Native
from binding import to_native,to_vmweave
r=json.loads((OUT/'correctness.json').read_text());passed={x['condition'] for x in r['conditions'] if x['status']=='PASS'}
conditions=[x for x in CONDITIONS if '-'.join(map(str,x)) in passed]
assert conditions,'No condition passed correctness gate'
s.IMAGES['worker']='localhost/vmweave-worker@'+c.admin(['chroot','/host','podman','image','inspect','localhost/vmweave-worker:ai-perf-persistent','--format','{{.Digest}}']).strip()
for block in range(1,6):
 order=['vmweave','passthrough'] if block%2 else ['passthrough','vmweave']
 cs=conditions[block-1:]+conditions[:block-1]
 for mode in order:
  name=f'ai-perf-{mode[0]}-b{block}-1016';dest=OUT/f'b{block}-{mode}'
  if dest.exists() and (dest/'complete.json').exists():continue
  v=VM(name) if mode=='vmweave' else Native(name)
  if mode=='passthrough':to_native()
  try:
   print('PREPARING',block,mode,flush=True);v.prepare()
   for condition in cs:
    measure(v,condition,'performance',dest/('-'.join(map(str,condition))))
   c.save(dest/'complete.json',{'block':block,'mode':mode,'conditions':cs,'utc':time.time()})
  finally:
   try:v.cleanup()
   finally:
    if mode=='passthrough':to_vmweave()
print('ALL FORMAL BLOCKS COMPLETE',flush=True)
