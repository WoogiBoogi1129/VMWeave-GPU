"""Preserve actual sessions/configuration, redact known credentials, and hash the bundle."""
import hashlib,re,shutil
from common import *
assert json.loads((OUT/'validation.json').read_text())['campaign_complete']
assert (OUT/'final-audit.json').exists()
for source in sorted(BASE.glob('*.terminal')):
 target=OUT/'terminal'/source.name;target.parent.mkdir(exist_ok=True)
 target.write_text(redact(source.read_text()))
for source in sorted(BASE.glob('build*.txt')):
 target=OUT/'build'/source.name;target.parent.mkdir(exist_ok=True)
 target.write_text(redact(source.read_text()))
history=[]
for pattern in ['collect-*.txt','first-shared-review-*.txt','recovery-checkpoint-*.txt','final-postprocess-*.txt']:
 for source in sorted(BASE.glob(pattern)):
  target=OUT/'analysis-history'/source.name;target.parent.mkdir(exist_ok=True)
  target.write_text(redact(source.read_text()))
  history.append({'file':target.name,'source_modified_utc':source.stat().st_mtime})
save(OUT/'analysis-history/index.json',{'scope':'Actual collection/analysis command outputs at successive checkpoints; early counts are partial, final outcomes are in validation.json and analysis/summary.json.','files':history})
for name in ['Worker.Containerfile','images.json']:
 source=BASE/name;target=OUT/'build'/name;target.write_text(redact(source.read_text()))
shutil.copy2(BASE/'artifacts/cubin-normalization.json',OUT/'build/cubin-normalization.json')
shutil.copy2(BASE/'processes.json',OUT/'monitoring/collectors.json')
for source in [BASE/'monitoring/prometheus.yml',BASE/'monitoring/grafana.ini',BASE/'monitoring/dashboards/performance.json',BASE/'monitoring/provisioning/datasources/prometheus.yaml']:
 target=OUT/'monitoring'/source.name;target.write_text(redact(source.read_text()))
# Original records may include application diagnostics as well as audited commands.
# Only the explicit secrets used by this campaign are replaced; record affected paths.
changed=[]
for file in sorted(OUT.rglob('*')):
 if not file.is_file() or file.suffix in ['.png','.gz','.bin']:continue
 try:text=file.read_text()
 except UnicodeDecodeError:continue
 cleaned=redact(text)
 if cleaned!=text:file.write_text(cleaned);changed.append(str(file.relative_to(OUT)))
 if re.search(r'-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----',cleaned):raise RuntimeError('Private key detected: '+str(file))
save(OUT/'redaction.json',{'scope':'Only campaign authentication literal values replaced with [REDACTED]; private keys/configuration never copied.','changed_paths_in_final_pass':changed,'utc':time.time()})
source=Path(__file__).parent
save(OUT/'analysis-source.json',{'commit_before_bundle_commit':call(['git','rev-parse','HEAD']).strip(),'files':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(source.iterdir()) if f.is_file()},'utc':time.time()})
# Hash after all audit output above; run this after every final bundle modification.
manifest=OUT/'SHA256SUMS'
manifest.write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(OUT))+'\n' for p in sorted(OUT.rglob('*')) if p.is_file() and p!=manifest))
print('Evidence finalized:',len(manifest.read_text().splitlines()),'files; credential values not printed.')
