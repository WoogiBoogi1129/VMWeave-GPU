"""Pilot-driven zero-spin candidate, without changing the measured binaries."""
from common import *
import tarfile
variants=json.loads((BASE/'variants.json').read_text())
save(OUT/'build/spin20-variants.json',variants)
for name in ['wait','both']:
    old=variants[name];cf=BASE/('Worker-'+name+'-spin0.Containerfile')
    cf.write_text('FROM '+old['worker']+'\nENV FLYT_SPIN_US=0\n')
    # Build from the equivalent local tag; imported OCI digest is a different
    # manifest representation in rootless storage.
    cf.write_text('FROM localhost/vmweave-worker:shmfirst-'+name+'-20261001\nENV FLYT_SPIN_US=0\n')
    tag='localhost/vmweave-worker:shmfirst-'+name+'-spin0-20261001'
    call(['podman','build','-f',cf,'-t',tag,BASE/'artifacts'],timeout=300)
    archive=BASE/('worker-'+name+'-spin0.oci')
    call(['podman','save','--format','oci-archive','-o',archive,tag],timeout=600)
    admin(['chroot','/host','podman','load','--input',archive],timeout=600)
    with tarfile.open(archive) as f:digest=json.load(f.extractfile('index.json'))['manifests'][0]['digest']
    variants[name]={**old,'worker':'localhost/vmweave-worker@'+digest,'spin_us':0}
    (OUT/'build'/cf.name).write_text(cf.read_text())
save(BASE/'variants.json',variants);save(OUT/'build/variants.json',variants)
