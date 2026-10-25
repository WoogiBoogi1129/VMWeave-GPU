import sys
import rodinia_campaign as h
label=sys.argv[1];s=None
try:
 s=h.prepare_vmw(label)
 if label=='qualification':h.measure(s,'qualification','gate')
 else:
  h.measure(s,'warmup',label);h.measure(s,'formal',label)
  if label=='r3':h.measure(s,'diagnostic',label)
finally:
 if not s and (h.B/'active-vmw.json').exists():
  import json
  candidate=json.loads((h.B/'active-vmw.json').read_text())
  if candidate['name']=='rodinia-w-1025-'+label:s=candidate
 if s:h.cleanup_vmw(s)
