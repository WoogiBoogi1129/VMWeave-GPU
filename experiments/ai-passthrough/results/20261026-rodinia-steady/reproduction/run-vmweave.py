import os
import sys,json
import measure as m
h=m.h;label=sys.argv[1];attempt=os.environ.get('RODINIA_ATTEMPT',label);s=None
try:
 s=h.prepare_vmw(attempt);m.measure(s,'qualification' if label.startswith('gate') else 'formal',label)
 if label=='r3':m.measure(s,'profile-gate',label,['nw'])
 if label=='r5':m.measure(s,'diagnostic',label)
finally:
 if not s and (h.B/'active-vmw.json').exists():
  candidate=json.loads((h.B/'active-vmw.json').read_text())
  if candidate['name']=='rodinia-w-1026-'+attempt:s=candidate
 if s:h.cleanup_vmw(s)
 h.drop_admin()
