"""Remove campaign credentials from captured provisioning evidence before publication."""
from common import *
values=set()
def visit(x):
 if isinstance(x,dict):
  for k,v in x.items():
   if k.lower() in ('password','token') and isinstance(v,str) and len(v)>=12:values.add(v)
   if k=='name' and 'PASSWORD' in str(v) and isinstance(x.get('value'),str):values.add(x['value'])
   visit(v)
 elif isinstance(x,list):
  for v in x:visit(v)
for p in BASE.glob('*.json'):
 try:visit(json.loads(p.read_text()))
 except (ValueError,UnicodeDecodeError):pass
values.discard('[REDACTED]');save(BASE/'redaction-values.json',sorted(values));(BASE/'redaction-values.json').chmod(0o600)
changed=[]
for p in OUT.rglob('*'):
 if not p.is_file():continue
 try:s=p.read_text()
 except UnicodeDecodeError:continue
 new=s
 for v in values:new=new.replace(v,'[REDACTED]')
 if new!=s:p.write_text(new);changed.append(str(p.relative_to(OUT)))
print(json.dumps({'credential_values_checked':len(values),'files_redacted':changed}))
