"""Build the selected defaults after formal eligibility review, retaining hashes."""
from common import *
import shutil,hashlib,tarfile
assert json.loads((OUT/'validation.json').read_text())['candidate_eligible']
source=(ROOT/'runtime/shm/shm-queue/src/perf.c').read_text()
assert 'bounded=!s||!strcmp(s,"bounded")' in source and 'optimized=!s||!strcmp(s,"optimized")' in source
dest=BASE/'final-artifacts';dest.mkdir(exist_ok=True)
for name in ['probe-S','load-S','work.ptx','guest-key','guest-key.pub']:shutil.copy2(BASE/'artifacts'/name,dest/name)
command='cmake -S /repo/runtime/shm -B /out/final-build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/out/final-artifacts && cmake --build /out/final-build -j 4 && cmake --install /out/final-build'
call(['taskset','-c','48-51','podman','run','--rm','-v',str(ROOT)+':/repo:ro','-v',str(BASE)+':/out','localhost/flyt-build:stage2-20260928','sh','-ec',command],timeout=600)
shutil.copy2(dest/'lib/libflyt_guest.so',dest/'libflyt_guest.so')
cf=BASE/'Worker-default.Containerfile';cf.write_text('FROM localhost/vmweave-worker:performance-20260930\nCOPY bin/flyt-shm-worker /opt/flyt/bin/flyt-shm-worker\nENV FLYT_METRICS=1\n')
tag='localhost/vmweave-worker:shmfirst-default-20261001';archive=BASE/'worker-default.oci'
call(['podman','build','-f',cf,'-t',tag,dest],timeout=600)
call(['podman','save','--format','oci-archive','-o',archive,tag],timeout=600)
admin(['chroot','/host','podman','load','-i',archive],timeout=600)
with tarfile.open(archive) as f:digest=json.load(f.extractfile('index.json'))['manifests'][0]['digest']
ref='localhost/vmweave-worker@'+digest
cid=admin(['chroot','/host','podman','create','--name','shmfirst-retain-default','--label','vmweave.campaign=shm-first-20261001','--entrypoint','/bin/true',ref]).strip()
refs=json.loads((BASE/'retained-images.json').read_text());refs.append({'name':'shmfirst-retain-default','container_id':cid,'image':ref});save(BASE/'retained-images.json',refs)
final={'worker':ref,'worker_sha256':hashlib.sha256((dest/'bin/flyt-shm-worker').read_bytes()).hexdigest(),
 'guest_sha256':hashlib.sha256((dest/'libflyt_guest.so').read_bytes()).hexdigest(),'source_commit':call(['git','rev-parse','HEAD']).strip(),
 'source_diff':call(['git','diff','--','runtime/shm']),'policy_overrides':False,'telemetry_enabled':True}
save(BASE/'final.json',final);save(OUT/'build/final.json',final);(OUT/'build'/cf.name).write_text(cf.read_text())
