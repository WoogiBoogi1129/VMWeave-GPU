"""Fix telemetry teardown before formal diagnostic trials; main stock runtime untouched."""
from common import *
import shutil,hashlib,tarfile
assert (OUT/'main-complete.json').exists()
assert GPU not in call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
# Final source v3 with disabled telemetry after dump; identical binary across followup variants.
src=BASE/'source/shm'
shutil.copy2(ROOT/'experiments/h2d-diagnosis/diag.c',src/'shm-queue/src/diag.c')
command='cmake -S /out/source/shm -B /out/build-final -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/out/final-diagnostic && cmake --build /out/build-final -j 4 && cmake --install /out/build-final'
call(['taskset','-c','48-51','podman','run','--rm','-v',str(BASE)+':/out','localhost/flyt-build:stage2-20260928','sh','-ec',command],timeout=600)
shutil.copy2(BASE/'final-diagnostic/lib/libflyt_guest.so',BASE/'diagnostic/libflyt_guest.so');shutil.copy2(BASE/'final-diagnostic/bin/flyt-shm-worker',BASE/'diagnostic/bin/flyt-shm-worker')
cf=BASE/'Worker-final.Containerfile';cf.write_text('FROM localhost/vmweave-worker:system-comparison-20261001\nCOPY bin/flyt-shm-worker /opt/flyt/bin/flyt-shm-worker\nENV HD_METRICS=1 HD_VARIANT=original\n')
tag='localhost/vmweave-worker:hd-final-20261005';archive=Path('/dev/shm/hd-final-20261005.oci')
call(['taskset','-c','48-51','podman','build','-f',cf,'-t',tag,BASE/'diagnostic'],timeout=600)
call(['taskset','-c','48-51','podman','save','--format','oci-archive','-o',archive,tag],timeout=600)
admin(['chroot','/host','podman','load','-i',archive],timeout=600)
with tarfile.open(archive) as f:digest=json.load(f.extractfile('index.json'))['manifests'][0]['digest']
ref='localhost/vmweave-worker@'+digest
cid=admin(['chroot','/host','podman','create','--name','hd-retain-final','--entrypoint','/bin/true',ref]).strip()
refs=json.loads((BASE/'retained-images.json').read_text());refs.append({'name':'hd-retain-final','container_id':cid,'image':ref});save(BASE/'retained-images.json',refs)
v=json.loads((BASE/'variants.json').read_text());v['original']=v['direct']=ref;save(BASE/'variants.json',v);save(OUT/'build/variants.json',v)
(OUT/'build/Worker-final.Containerfile').write_text(cf.read_text())
save(OUT/'build/final-runtime-hashes.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [BASE/'diagnostic/bin/flyt-shm-worker',BASE/'diagnostic/libflyt_guest.so']})
