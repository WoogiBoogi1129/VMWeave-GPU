"""Build/import identical runtime binaries with independent policy settings."""
from common import *
import hashlib
import tarfile

OUT.mkdir(parents=True,exist_ok=True)
ensure_admin()
variants={}
for name,wait_mode,copy_mode in [('base','legacy','legacy'),('wait','bounded','legacy'),('copy','legacy','optimized'),('both','bounded','optimized')]:
    containerfile=BASE/('Worker-'+name+'.Containerfile')
    containerfile.write_text('FROM localhost/vmweave-worker:performance-20260930\n'
      'COPY bin/flyt-shm-worker /opt/flyt/bin/flyt-shm-worker\n'
      'ENV FLYT_WAIT_MODE='+wait_mode+' FLYT_COPY_MODE='+copy_mode+' FLYT_METRICS=1\n')
    tag='localhost/vmweave-worker:shmfirst-'+name+'-20261001'
    call(['podman','build','-f',containerfile,'-t',tag,BASE/'artifacts'],timeout=600)
    archive=BASE/('worker-'+name+'.oci')
    if not archive.exists():call(['podman','save','--format','oci-archive','-o',archive,tag],timeout=600)
    admin(['chroot','/host','podman','load','--input',archive],timeout=900)
    with tarfile.open(archive) as bundle:
        digest=json.load(bundle.extractfile('index.json'))['manifests'][0]['digest']
    variants[name]={'worker':'localhost/vmweave-worker@'+digest,'wait':wait_mode,'copy':copy_mode}
    save(BASE/'variants.json',variants)
    (OUT/'build').mkdir(exist_ok=True)
    (OUT/'build'/containerfile.name).write_text(containerfile.read_text())
save(OUT/'build/variants.json',variants)
save(OUT/'build/artifact-hashes.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [BASE/'artifacts/bin/flyt-shm-worker',BASE/'artifacts/libflyt_guest.so',BASE/'artifacts/probe-S']})
