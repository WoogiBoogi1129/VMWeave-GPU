"""Same Worker executable with diagnostic telemetry disabled; between sessions only."""
from common import *
import tarfile,hashlib
assert GPU not in call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
cf=BASE/'Worker-off.Containerfile';cf.write_text('FROM localhost/vmweave-worker:hd-final-20261005\nENV HD_METRICS=0\n')
tag='localhost/vmweave-worker:hd-off-20261005';archive=Path('/dev/shm/hd-off-20261005.oci')
call(['taskset','-c','48-51','podman','build','-f',cf,'-t',tag,BASE/'diagnostic'],timeout=600)
call(['taskset','-c','48-51','podman','save','--format','oci-archive','-o',archive,tag],timeout=600)
admin(['chroot','/host','podman','load','-i',archive],timeout=600)
with tarfile.open(archive) as f:digest=json.load(f.extractfile('index.json'))['manifests'][0]['digest']
ref='localhost/vmweave-worker@'+digest
cid=admin(['chroot','/host','podman','create','--name','hd-retain-off','--entrypoint','/bin/true',ref]).strip()
refs=json.loads((BASE/'retained-images.json').read_text());refs.append({'name':'hd-retain-off','container_id':cid,'image':ref});save(BASE/'retained-images.json',refs)
v=json.loads((BASE/'variants.json').read_text());v['original-off']=v['direct-off']=ref;save(BASE/'variants.json',v);save(OUT/'build/variants.json',v)
(OUT/'build/Worker-off.Containerfile').write_text(cf.read_text())
save(OUT/'build/off.json',{'worker_sha256':hashlib.sha256((BASE/'diagnostic/bin/flyt-shm-worker').read_bytes()).hexdigest(),'image':ref,'metrics':False})
