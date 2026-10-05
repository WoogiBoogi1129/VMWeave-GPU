from common import *
import shutil,tarfile,hashlib
ensure_admin()
images=json.loads((BASE/'images.json').read_text())
refs=[('worker',images['worker'],ROOT/'.local/system-comparison-20261001/worker.oci'),('guest',GUEST,ROOT/'.local/pytorch-path-20260922/guest-16g.oci'),('launcher','localhost/flyt-virt-launcher@sha256:3a63c98b5a178af7f58f8979e09cbd11182f7220e5826f5048efb22a2d7b7935',ROOT/'.local/implementation-20260922/launcher-v2.oci'),('hook',images['hook'],Path('/dev/shm/vmweave-hook.oci')),('cell',images['cell'],ROOT/'.local/performance-20260930/cell.oci'),('manager',images['manager'],ROOT/'.local/performance-20260930/manager.oci'),('helper',images['helper'],Path('/dev/shm/vmweave-helper.oci')),('mongo',images['mongo'],None)]
records=json.loads((BASE/'retained-images.json').read_text()) if (BASE/'retained-images.json').exists() else []
for label,ref,archive in refs:
 if any(x['name']=='hd-retain-'+label for x in records):continue
 if not admin(['chroot','/host','podman','image','inspect','--format','{{.Id}}',ref],check=False).strip():
  if archive is None:
   admin(['nsenter','--net=/host/proc/1/ns/net','chroot','/host','podman','pull',ref],timeout=600)
  else:
   admin(['chroot','/host','podman','load','-i',archive],timeout=600)
 name='hd-retain-'+label
 cid=admin(['chroot','/host','podman','create','--name',name,'--label','vmweave.campaign=h2d-diagnosis-20261005','--entrypoint','/bin/true',ref]).strip()
 records.append({'name':name,'container_id':cid,'image':ref});save(BASE/'retained-images.json',records)
for path in ['S','T']:shutil.copy2(BASE/'artifacts'/('probe-'+path),BASE/'artifacts'/('original-probe-'+path))
# Snapshot prior evidence by tracked blob + working tree hash.
files=list((ROOT/'experiments/evidence/results/2026-10-01-system-comparison').rglob('*'))
save(OUT/'prior-sha256.json',{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()})
