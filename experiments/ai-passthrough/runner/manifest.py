"""Generate or verify hashes of tracked campaign evidence and documentation."""
import hashlib,json,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];root=R.parents[1];target=R/'artifact-manifest.json'
files=[root/p for p in subprocess.check_output(['git','ls-files','--',str(R.relative_to(root))],cwd=root,text=True).splitlines() if root/p!=target]
assert not any(p.suffix=='.pt' or p.name=='known-hosts' or '__pycache__' in p.parts for p in files)
rows=[{'path':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)]
if '--check' in sys.argv:
 assert json.loads(target.read_text())['files']==rows
 print(f'PASS: {len(rows)} artifact hashes')
else:
 target.write_text(json.dumps({'algorithm':'sha256','scope':'Tracked experiment files excluding this manifest; local large tensors intentionally excluded','files':rows},indent=2)+'\n')
