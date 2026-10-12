"""Validate the E2 bundle before creating any VM. No GPU operations."""
import hashlib,json,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BUNDLE=ROOT/'.local/thesis-isolation-20261012/guest-python-cuda.tgz'
MANIFEST=ROOT/'experiments/thesis-isolation/config/e2-environment.json'
def sha256(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
 return h.hexdigest()
def validate():
 data=json.loads(MANIFEST.read_text())
 if sha256(BUNDLE)!=data['bundle_sha256']:raise ValueError('E2 bundle hash mismatch')
 with tarfile.open(BUNDLE,'r|gz') as archive:
  names=set()
  for member in archive:
   name=member.name
   if name.startswith('/') or '..' in Path(name).parts:raise ValueError('Invalid archive path')
   if not (name=='opt/torch-venv' or name.startswith('opt/torch-venv/') or name=='opt/flyt-cuda-libs' or name.startswith('opt/flyt-cuda-libs/')):raise ValueError('Unexpected archive member: '+name)
   names.add(name)
 for required in data['required_members']:
  if required not in names:raise ValueError('Missing archive member: '+required)
 return data
if __name__=='__main__':print(json.dumps(validate(),indent=2))
