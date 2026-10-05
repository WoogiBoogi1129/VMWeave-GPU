from common import *
import shutil,hashlib,tarfile
command='cmake -S /out/source/shm -B /out/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/out/diagnostic && cmake --build /out/build -j 4 && cmake --install /out/build'
call(['taskset','-c','48-51','podman','run','--rm','-v',str(BASE)+':/out','localhost/flyt-build:stage2-20260928','sh','-ec',command],timeout=600)
shutil.copy2(BASE/'diagnostic/lib/libflyt_guest.so',BASE/'diagnostic/libflyt_guest.so')
command="gcc -O2 -DFLYT_GUEST -I/usr/local/cuda/include /repo/experiments/h2d-diagnosis/probe.c -L/out/artifacts -Wl,-rpath,'$ORIGIN' -lflyt_guest -o /out/diagnostic/probe-S\ngcc -O2 -DFLYT_TCP -I/usr/local/cuda/include /repo/experiments/h2d-diagnosis/probe.c -L/out/artifacts -Wl,-rpath,'$ORIGIN' -Wl,-rpath-link,/out/artifacts -Wl,--allow-shlib-undefined -l:cricket-client.so -o /out/diagnostic/probe-T"
call(['taskset','-c','48-51','podman','run','--rm','-v',str(ROOT)+':/repo:ro','-v',str(BASE)+':/out','localhost/flyt-build:stage2-20260928','sh','-ec',command],timeout=600)
variants={}
for variant in ['original','reuse','pinned','unroll','chunk']:
 cf=BASE/('Worker-'+variant+'.Containerfile');cf.write_text('FROM localhost/vmweave-worker:system-comparison-20261001\nCOPY bin/flyt-shm-worker /opt/flyt/bin/flyt-shm-worker\nENV HD_METRICS=1 HD_VARIANT='+variant+'\n')
 tag='localhost/vmweave-worker:hd2-'+variant+'-20261005';archive=Path('/dev/shm')/('hd2-20261005-'+variant+'.oci')
 call(['podman','build','-f',cf,'-t',tag,BASE/'diagnostic'],timeout=600)
 call(['podman','save','--format','oci-archive','-o',archive,tag],timeout=600)
 admin(['chroot','/host','podman','load','-i',archive],timeout=600)
 with tarfile.open(archive) as f:digest=json.load(f.extractfile('index.json'))['manifests'][0]['digest']
 ref='localhost/vmweave-worker@'+digest
 cid=admin(['chroot','/host','podman','create','--name','hd2-retain-'+variant,'--entrypoint','/bin/true',ref]).strip()
 refs=json.loads((BASE/'retained-images.json').read_text());refs.append({'name':'hd2-retain-'+variant,'container_id':cid,'image':ref});save(BASE/'retained-images.json',refs)
 variants[variant]=ref;save(BASE/'variants.json',variants)
 save(OUT/'build/variants.json',variants)
 (OUT/'build'/cf.name).write_text(cf.read_text())
save(OUT/'build/diagnostic-hashes.json',{str(p.relative_to(BASE/'diagnostic')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (BASE/'diagnostic').rglob('*') if p.is_file()})
