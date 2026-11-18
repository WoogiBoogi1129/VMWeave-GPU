"""Seal only the public campaign directory after report review."""
from pathlib import Path
import hashlib,json,re
P=Path(__file__).resolve().parents[1]
files=[p for p in sorted(P.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.pyc','.pyo'] and p.name not in ['SHA256SUMS','bundle.json']]
assert (P/'REPORT.md').exists()
assert json.loads((P/'analysis/independent-verification.json').read_text())['passed']
assert json.loads((P/'evidence/cleanup-complete.json').read_text())['namespace_removed']
for p in files:
 assert p.stat().st_size<100*1024*1024,('GitHub file limit',str(p))
 if p.suffix in ['.gz','.png','.bin']:continue
 t=p.read_text(errors='replace')
 assert not re.search(r'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----',t),p
 assert not re.search(r'\b(?:ghp_|github_pat_|hf_)[A-Za-z0-9_]{24,}',t),p
 assert not re.search(r'\bAKIA[0-9A-Z]{16}\b',t),p
bundle={'files_without_manifest':len(files),'bytes_without_manifest':sum(p.stat().st_size for p in files),'raw_format':'gzip uint64 little-endian nanoseconds','integrity':'SHA256SUMS covers all publication files except itself; Python bytecode excluded','secret_checks':['private-key headers','GitHub/Hugging Face token patterns','AWS access key pattern'],'private_data':'Original operating snapshots remain outside this directory; temporary experiment SSH keys and Mongo credentials were deleted.'}
(P/'bundle.json').write_text(json.dumps(bundle,indent=2)+'\n');files.append(P/'bundle.json')
(P/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(P))+'\n' for p in sorted(files)))
print(json.dumps(bundle,indent=2))
