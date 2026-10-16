"""Stage only reviewed source, report and evidence files; never push or commit."""
import json,re,hashlib,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];E=P/'evidence/20261016'
s=json.loads((E/'summary.json').read_text());assert s['final'] and s['single_count']==s['pair_count']==s['torch_count']==10
(P/'.gitignore').write_text('# Full cluster/command snapshots remain local; selected immutable evidence is tracked explicitly.\n/results/\n')
files=set(P.glob('*.py'))|set(P.glob('*.c'))|set(P.glob('*.cjs'))|set(P.glob('*.json'))|{P/'README.md',P/'.gitignore'}
files.update(f for f in E.rglob('*') if f.is_file())
for rel,sha in json.loads((E/'raw-sha256.json').read_text()).items():
 f=P/rel;assert hashlib.sha256(f.read_bytes()).hexdigest()==sha,rel;files.add(f)
for link in re.findall(r'\]\(([^)#]+)(?:#[^)]*)?\)',(P/'README.md').read_text()):
 if '://' not in link:assert (P/link).exists(),link
# Preserve separate pilot evidence without mixing it into formal repetition counts.
for d in (P/'results/20261016/runs').glob('vram-pilot-*'):
 for name in ['summary.json','events.jsonl','accounting.jsonl','cleanup.json','channel-released.json']:
  if (d/name).exists():files.add(d/name)
source={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files) if p.suffix in ('.py','.c','.cjs')}
(E/'source-sha256.json').write_text(json.dumps(source,indent=2)+'\n');files.add(E/'source-sha256.json')
manifest={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files) if p!=E/'artifact-sha256.json'}
(E/'artifact-sha256.json').write_text(json.dumps(manifest,indent=2)+'\n');files.add(E/'artifact-sha256.json')
subprocess.run(['git','add','-f',*[str(f.relative_to(ROOT)) for f in sorted(files)]],cwd=ROOT,check=True)
print('Curated',len(files),'files;',sum(f.stat().st_size for f in files),'bytes; links and raw hashes verified')
