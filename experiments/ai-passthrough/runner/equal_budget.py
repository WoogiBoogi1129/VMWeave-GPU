"""Supplement: 12 host CPUs in both modes, three pairs at two extremes."""
import time,json
from campaign import c,s,BASE,OUT,VM,measure
from passthrough_guest import Native
from binding import to_native,to_vmweave
conditions=[('small',32,'resident'),('medium',1024,'resident')]
passed={x['condition'] for x in json.loads((OUT/'correctness.json').read_text())['conditions'] if x['status']=='PASS'}
assert all('-'.join(map(str,x)) in passed for x in conditions)
s.IMAGES['worker']='localhost/vmweave-worker@'+c.admin(['chroot','/host','podman','image','inspect','localhost/vmweave-worker:ai-perf-persistent','--format','{{.Digest}}']).strip()
for b in range(1,4):
 for mode in (['vmweave','passthrough'] if b%2 else ['passthrough','vmweave']):
  name=f'ai-perf-eq-{mode[0]}-{b}-1016';v=VM(name) if mode=='vmweave' else Native(name,cores=12);dest=OUT/'equal-budget'/f'b{b}-{mode}'
  if mode=='passthrough':to_native()
  try:
   v.prepare()
   for condition in (conditions if b%2 else conditions[::-1]):measure(v,condition,'performance',dest/('-'.join(map(str,condition))))
   c.save(dest/'complete.json',{'block':b,'mode':mode,'host_cpu_budget':12,'guest_vcpus':8 if mode=='vmweave' else 12,'utc':time.time()})
  finally:
   try:v.cleanup()
   finally:
    if mode=='passthrough':to_vmweave()
