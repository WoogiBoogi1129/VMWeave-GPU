"""Reject credential leaks and oversized files before publishing evidence."""
from common import *
import gzip,lzma,hashlib
assert (BASE/'stop-monitor').exists()
os.sched_setaffinity(0,{48,49,50,51})
values=json.loads((BASE/'redaction-values.json').read_text())
count=0;total=0;largest=[]
for p in OUT.rglob('*'):
 if not p.is_file() or p.name=='SHA256SUMS':continue
 raw=p.read_bytes();total+=len(raw);count+=1;largest.append((len(raw),str(p.relative_to(OUT))))
 if p.suffix=='.xz':raw=lzma.decompress(raw)
 elif p.suffix=='.gz':raw=gzip.decompress(raw)
 assert all(v.encode() not in raw for v in values),('Credential leak',p)
 assert b'-----BEGIN OPENSSH PRIVATE KEY-----' not in raw and b'-----BEGIN PRIVATE KEY-----' not in raw and b'-----BEGIN RSA PRIVATE KEY-----' not in raw,p
 assert p.stat().st_size<50_000_000,('Oversized Git file',p)
save(OUT/'publication-check.json',{'files_scanned':count,'bytes':total,'known_credentials_scanned':len(values),'credential_leaks':0,'private_key_markers':0,'maximum_file_bytes':max(n for n,_ in largest),'largest_files':[{'bytes':n,'path':p} for n,p in sorted(largest,reverse=True)[:10]],'storage':'Compressed evidence is committed to Git; no ephemeral Actions-only artifact dependency.'})
lines=[]
for p in sorted(OUT.rglob('*')):
 if p.is_file() and p.name!='SHA256SUMS':lines.append(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(OUT)))
(OUT/'SHA256SUMS').write_text('\n'.join(lines)+'\n')
print('PASS:',count,'files scanned;',round(total/1048576,2),'MiB')
