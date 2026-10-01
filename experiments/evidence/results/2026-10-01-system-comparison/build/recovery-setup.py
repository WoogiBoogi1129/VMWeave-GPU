import sys,hashlib
sys.path.insert(0,'experiments/system-comparison')
from common import *
records=json.loads((BASE/'retained-images.json').read_text());images=json.loads((BASE/'images.json').read_text());images['worker']=records[0]['image']
mongo='docker.io/library/mongo:7.0'
admin(['nsenter','--net=/host/proc/1/ns/net','chroot','/host','podman','pull',mongo],timeout=600)
obj=json.loads(admin(['chroot','/host','podman','image','inspect',mongo]))[0];images['mongo']=next(x for x in obj['RepoDigests'] if 'mongo@sha256:' in x)
for label,ref in [('mongo',images['mongo']),('helper',images['helper'])]:
 cid=admin(['chroot','/host','podman','create','--name','sc-retain-'+label,'--label','vmweave.campaign=system-comparison-20261001','--entrypoint','/bin/true',ref]).strip()
 records.append({'name':'sc-retain-'+label,'container_id':cid,'image':ref})
save(BASE/'retained-images.json',records);save(OUT/'retained-images.json',records)
save(BASE/'images.json',images);save(OUT/'build/images.json',images)
save(OUT/'build/artifact-hashes.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [*(BASE/'artifacts').glob('*.so'),BASE/'artifacts/bin/flyt-shm-worker',BASE/'artifacts/probe-S',BASE/'artifacts/probe-T',BASE/'artifacts/work.ptx',BASE/'artifacts/work.cubin']})
(OUT/'build/Worker.Containerfile').write_text((BASE/'Worker.Containerfile').read_text())
