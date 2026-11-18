"""Remove campaign-only staging files after all runtime resources are gone."""
from common import *
import shutil
def cleanup_private_storage():
 state=json.loads((O/'evidence/cleanup-complete.json').read_text())
 assert state['namespace_removed'] and state['experiment_vms_removed']
 assert B==R/'.local/communication-20261117'
 names=['flyt-cell.oci','flyt-manager.oci','noble-server-cloudimg-amd64.img','guest-key','guest-key.pub','known-hosts']
 rows=[]
 for name in names:
  p=B/name
  assert not p.is_symlink(),str(p)
  size=p.stat().st_size if p.exists() else 0
  p.unlink(missing_ok=True)
  rows.append({'name':name,'bytes_removed':size,'absent':not p.exists()})
 cfg=B/'flyt-config'
 assert not cfg.is_symlink()
 size=sum(p.stat().st_size for p in cfg.rglob('*') if p.is_file()) if cfg.exists() else 0
 if cfg.exists():shutil.rmtree(cfg)
 rows.append({'name':'flyt-config','bytes_removed':size,'absent':not cfg.exists()})
 result={'utc':time.time(),'removed':rows,'scope':'Only campaign staging copies and temporary credentials. Original rootless Flyt images, compiled artifact provenance and private baseline backup retained.'}
 save(O/'evidence/private-workspace-cleanup.json',result)
 print(json.dumps(result,indent=2))
if __name__=='__main__':cleanup_private_storage()
