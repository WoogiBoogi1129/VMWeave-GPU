from common import *
source=(ROOT/'tests/integration/queue_payload_bounds.c').read_text().replace('../../runtime/shm/shm-queue/src/queue.c',str(BASE/'source/shm/shm-queue/src/queue.c')).replace(' puts("PASS:', ' hd_cleanup();hd_dump("test");\n puts("PASS:')
(BASE/'queue-test-v2.c').write_text(source)
q=BASE/'source/shm/shm-queue';h=BASE/'source/shm/shm-contract/include'
call(['gcc','-O1','-g','-fsanitize=address,undefined','-I'+str(q/'include'),'-I'+str(h),BASE/'queue-test-v2.c',q/'src/perf.c',q/'src/diag.c','-pthread','-ldl','-o',BASE/'queue-test-v2'])
for v in ['original','reuse','unroll','chunk']:
 result=call(['env','ASAN_OPTIONS=halt_on_error=1','UBSAN_OPTIONS=halt_on_error=1','HD_METRICS=1','HD_VARIANT='+v,BASE/'queue-test-v2'])
 (OUT/'build'/('queue-'+v+'-asan.txt')).write_text(result)
save(OUT/'build/queue-validation.json',{'asan_ubsan_pass':['original','reuse','unroll','chunk'],'pinned':'Must pass actual VM CUDA pilot separately; not simulated by this CPU-only test.'})
