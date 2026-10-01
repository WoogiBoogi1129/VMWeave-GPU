"""Finalize safe public logs and verify immutable prior evidence."""
from common import *
import hashlib,shutil,gzip
assert json.loads((OUT/'validation.json').read_text())['complete']
assert (OUT/'cleanup-complete.json').exists()
dest=OUT/'terminal';dest.mkdir(exist_ok=True)
for name in ['build.terminal','pilot.terminal','pilot-ready.terminal','formal.terminal']:
 shutil.copy2(BASE/name,dest/name)
for name in ['preflight.txt','build-driver.txt','pilot-driver.txt','pilot-ready-driver.txt','analysis.txt','docs-build.txt','cleanup-driver.txt','final-audit.txt','grafana-capture.txt','terminal-capture.txt']:
 shutil.copy2(BASE/name,OUT/'build'/name)
prior=[]
for relative in ['experiments/evidence/results/2026-09-30-performance','experiments/evidence/results/2026-10-01-shm-first','experiments/diagnostics/2026-10-01-shm-latency']:
 p=ROOT/relative;count=0
 for line in (p/'SHA256SUMS').read_text().splitlines():
  digest,name=line.split(None,1);assert hashlib.sha256((p/name.lstrip('*')).read_bytes()).hexdigest()==digest,name;count+=1
 prior.append({'bundle':relative,'files_verified':count,'unchanged':True})
save(OUT/'prior-evidence-integrity.json',prior)
password=json.loads((BASE/'legacy-auth.json').read_text())['password'].encode()
for f in OUT.rglob('*'):
 if not f.is_file() or f.suffix=='.png':continue
 data=gzip.open(f,'rb').read() if f.suffix=='.gz' else f.read_bytes()
 assert password not in data,f
 assert not any(x in data for x in [b'-----BEGIN OPENSSH PRIVATE KEY-----',b'-----BEGIN RSA PRIVATE KEY-----',b'github_pat_',b'ghp_']),f
save(OUT/'source-final.json',{'parent_commit':call(['git','rev-parse','HEAD']).strip(),'runtime_source_commit':json.loads((OUT/'protocol.json').read_text())['runtime_source_commit'],'harness_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.iterdir() if p.suffix in ['.py','.c','.cjs']},'note':'The enclosing Git commit contains this final source and evidence. Terminal automation and post-run inspection are not claimed to be manual human execution.'})
files=sorted(p for p in OUT.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
(OUT/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(OUT).as_posix()+'\n' for p in files))
print('Archived',len(files),'evidence files; prior checksums preserved and credential scan passed')
