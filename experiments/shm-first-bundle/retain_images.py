"""Temporary stopped image-reference containers, no GPU/VM execution.

The node's existing image GC evicts unused local-only digests between sessions.
Keep exact images referenced for this campaign; remove only recorded IDs later.
"""
from common import *
variants=json.loads((BASE/'variants.json').read_text())
images=[(v,variants[v]['worker'],BASE/('worker-'+v+('-spin0' if v in ['wait','both'] else '')+'.oci')) for v in variants]
images += [('guest',GUEST,ROOT/'.local/pytorch-path-20260922/guest-16g.oci'),
 ('launcher','localhost/flyt-virt-launcher@sha256:3a63c98b5a178af7f58f8979e09cbd11182f7220e5826f5048efb22a2d7b7935',ROOT/'.local/implementation-20260922/launcher-v2.oci'),
 ('hook',json.loads((BASE/'images.json').read_text())['hook'],Path('/dev/shm/vmweave-hook.oci'))]
records=[]
for label,image,archive in images:
 name='shmfirst-retain-'+label
 existing=admin(['chroot','/host','podman','container','inspect','--format','{{.Id}}',name],check=False).strip()
 if not existing:
  present=admin(['chroot','/host','podman','image','inspect','--format','{{.Id}}',image],check=False).strip()
  if not present:admin(['chroot','/host','podman','load','-i',archive],timeout=600)
  existing=admin(['chroot','/host','podman','create','--name',name,'--label','vmweave.campaign=shm-first-20261001','--entrypoint','/bin/true',image],timeout=120).strip()
 records.append({'name':name,'container_id':existing,'image':image})
 save(BASE/'retained-images.json',records)
save(OUT/'retained-images.json',records)
