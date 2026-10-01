"""Keep the measured SHM runtime and legacy TCP stack; rebuild only the probe."""
from common import *
import hashlib,tarfile
ensure_admin()
command='''gcc -O2 -DFLYT_GUEST -I/usr/local/cuda/include /repo/experiments/system-comparison/probe.c -L/out -Wl,-rpath,'$ORIGIN' -lflyt_guest -o /out/probe-S
gcc -O2 -DFLYT_TCP -I/usr/local/cuda/include /repo/experiments/system-comparison/probe.c -L/out -Wl,-rpath,'$ORIGIN' -Wl,-rpath-link,/out -Wl,--allow-shlib-undefined -l:cricket-client.so -o /out/probe-T'''
call(['taskset','-c','48-51','podman','run','--rm','-v',str(ROOT)+':/repo:ro','-v',str(BASE/'artifacts')+':/out','localhost/flyt-build:stage2-20260928','sh','-ec',command],timeout=600)
cf=BASE/'Worker.Containerfile';cf.write_text('FROM localhost/vmweave-worker:shmfirst-default-20261001\nENV FLYT_METRICS=0\n')
tag='localhost/vmweave-worker:system-comparison-20261001';archive=BASE/'worker.oci'
call(['podman','build','-f',cf,'-t',tag,BASE/'artifacts'],timeout=600)
call(['podman','save','--format','oci-archive','-o',archive,tag],timeout=600)
with tarfile.open(archive) as f:digest=json.load(f.extractfile('index.json'))['manifests'][0]['digest']
images=json.loads((BASE/'images.json').read_text());images['worker']='localhost/vmweave-worker@'+digest
refs=[('worker',images['worker'],archive),('guest',GUEST,ROOT/'.local/pytorch-path-20260922/guest-16g.oci'),
 ('launcher','localhost/flyt-virt-launcher@sha256:3a63c98b5a178af7f58f8979e09cbd11182f7220e5826f5048efb22a2d7b7935',ROOT/'.local/implementation-20260922/launcher-v2.oci'),
 ('hook',images['hook'],Path('/dev/shm/vmweave-hook.oci')),
 ('cell',images['cell'],ROOT/'.local/performance-20260930/cell.oci'),
 ('manager',images['manager'],ROOT/'.local/performance-20260930/manager.oci'),
 ('helper',images['helper'],None)]
records=[]
for label,ref,archive in refs:
 if not admin(['chroot','/host','podman','image','inspect','--format','{{.Id}}',ref],check=False).strip():
  if archive is None:raise RuntimeError('Provision the recorded helper image before this campaign: '+ref)
  admin(['chroot','/host','podman','load','-i',archive],timeout=600)
 cid=admin(['chroot','/host','podman','create','--name','sc-retain-'+label,'--label','vmweave.campaign=system-comparison-20261001','--entrypoint','/bin/true',ref]).strip()
 records.append({'name':'sc-retain-'+label,'container_id':cid,'image':ref});save(BASE/'retained-images.json',records)
mongo='docker.io/library/mongo:7.0'
if not admin(['chroot','/host','podman','image','inspect','--format','{{.Id}}',mongo],check=False).strip():admin(['nsenter','--net=/host/proc/1/ns/net','chroot','/host','podman','pull',mongo],timeout=600)
obj=json.loads(admin(['chroot','/host','podman','image','inspect',mongo]))[0]
images['mongo']=next(x for x in obj['RepoDigests'] if 'mongo@sha256:' in x)
cid=admin(['chroot','/host','podman','create','--name','sc-retain-mongo','--label','vmweave.campaign=system-comparison-20261001','--entrypoint','/bin/true',images['mongo']]).strip()
records.append({'name':'sc-retain-mongo','container_id':cid,'image':images['mongo']})
save(BASE/'retained-images.json',records);save(OUT/'retained-images.json',records)
save(BASE/'images.json',images);save(OUT/'build/images.json',images)
save(OUT/'build/artifact-hashes.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [*(BASE/'artifacts').glob('*.so'),BASE/'artifacts/bin/flyt-shm-worker',BASE/'artifacts/probe-S',BASE/'artifacts/probe-T',BASE/'artifacts/work.ptx',BASE/'artifacts/work.cubin']})
(OUT/'build/Worker.Containerfile').write_text(cf.read_text())
