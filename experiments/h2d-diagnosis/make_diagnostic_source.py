"""Generate isolated instrumented runtime; production sources stay unchanged."""
from common import *
import shutil
src=BASE/'source/shm'
assert not src.exists()
shutil.copytree(ROOT/'runtime/shm',src)
q=src/'shm-queue'
shutil.copy2(Path(__file__).with_name('diag.h'),q/'include/hd_diag.h')
shutil.copy2(Path(__file__).with_name('diag.c'),q/'src/diag.c')
p=q/'CMakeLists.txt';s=p.read_text();s += '\ntarget_sources(flyt_shm_queue PRIVATE src/diag.c)\ntarget_link_libraries(flyt_shm_queue PUBLIC dl)\n';p.write_text(s)
def edit(rel, pairs):
 p=src/rel;s=p.read_text();s='#include "hd_diag.h"\n'+s
 for old,new in pairs:
  assert old in s,(rel,old);s=s.replace(old,new)
 p.write_text(s)
edit('shm-queue/src/queue.c',[
 ('if (q->input_bytes) memcpy(c->request_payload, q->input, q->input_bytes);','uint64_t hd=hd_now();if (q->input_bytes) memcpy(c->request_payload, q->input, q->input_bytes);hd_record(2,q->request_id,q->input_bytes,hd);'),
 ('payload = malloc((size_t)r.bytes);','uint64_t hd=hd_now();payload = hd_alloc((size_t)r.bytes);hd_record(3,r.id,r.bytes,hd);'),
 ('payload_snapshot(payload, c->request_payload + r.offset, (size_t)r.bytes);','hd=hd_now();payload_snapshot(payload, c->request_payload + r.offset, (size_t)r.bytes);hd_record(4,r.id,r.bytes,hd);'),
 ('free((void *)q->input);','hd_free((void *)q->input);'),
])
edit('src/guest.c',[
 ('size_t capacity,received;int result;', 'size_t capacity,received;int result;uint64_t rid;'),
 ('job.result=exchange(c,identity,&id,job.api,','job.rid=id;job.result=exchange(c,identity,&id,job.api,'),
 ('if(flyt_shm_submit(c,&q))','uint64_t hd=hd_now();if(flyt_shm_submit(c,&q))'),
 ('++*id;*got=r.output_bytes;','hd_record(5,*id,n,hd);++*id;*got=r.output_bytes;'),
 ('flyt_shm_close(c);flyt_unmap(&m);return NULL;','hd_dump("guest-io");flyt_shm_close(c);flyt_unmap(&m);return NULL;'),
 ('flyt_perf_dump("guest-caller");','hd_dump("guest-caller");flyt_perf_dump("guest-caller");'),
 ('if(kind==cudaMemcpyHostToDevice&&n)memcpy(in+48,src,n);','uint64_t hd=hd_now();if(kind==cudaMemcpyHostToDevice&&n)memcpy(in+48,src,n);uint64_t hd_end=hd_now();'),
 ('if(!e&&got!=(kind==cudaMemcpyDeviceToHost?n:0))','if(hd&&kind==cudaMemcpyHostToDevice){/* record exact pack interval after ID assignment */hd_pack_record(job.rid,n,hd,hd_end);}\n    if(!e&&got!=(kind==cudaMemcpyDeviceToHost?n:0))'),
])
# All diagnostic helper functions are defined in diag.c.
edit('src/worker.c',[
 ('memset(&idle,0,sizeof(idle));','memset(&idle,0,sizeof(idle));hd_set_id(q.request_id);uint64_t hd=hd_now();'),
 ('rc=flyt_shm_worker_respond(channel,&r);','hd_record(6,q.request_id,q.input_bytes,hd);hd=hd_now();rc=flyt_shm_worker_respond(channel,&r);hd_record(7,q.request_id,r.output_bytes,hd);'),
 ('done:\n','done:\n    hd_dump("worker");hd_cleanup();\n'),
])
# runtime backend links queue explicitly for diagnostic symbols/include
p=src/'CMakeLists.txt';p.write_text(p.read_text()+'\ntarget_link_libraries(flyt_cuda_runtime PUBLIC flyt_shm_queue)\n')
edit('cuda-dispatch/src/runtime.c',[
 ('return (uint32_t)cudaMemcpy(dst, src, bytes, kind);','uint64_t hd=hd_now();uint32_t e=(uint32_t)cudaMemcpy(dst,src,bytes,kind);hd_record(direction==FLYT_COPY_HTOD?8:9,hd_id(),bytes,hd);return e;'),
 ('return (uint32_t)cudaDeviceSynchronize();','uint64_t hd=hd_now();uint32_t e=(uint32_t)cudaDeviceSynchronize();hd_record(10,hd_id(),0,hd);return e;'),
])
call(['diff','-ruN',ROOT/'runtime/shm',src],check=False)
(OUT/'build').mkdir(exist_ok=True)
(OUT/'build/runtime-diagnostic.patch').write_text(call(['diff','-ruN',ROOT/'runtime/shm',src],check=False))

# Single-variable copy experiments selected after the first instrumented pilot.
p=src/'src/guest.c';s=p.read_text();old='if(kind==cudaMemcpyHostToDevice&&n)memcpy(in+48,src,n);'
assert old in s
s=s.replace(old,'if(kind==cudaMemcpyHostToDevice&&n){if(hd_variant()==4){for(size_t k=0;k<n;k+=1048576){size_t z=n-k<1048576?n-k:1048576;memcpy(in+48+k,(const unsigned char*)src+k,z);}}else memcpy(in+48,src,n);}')
p.write_text(s)
p=q/'src/queue.c';s=p.read_text();old='while(n>=8){uint64_t v=*(const volatile alias_word *)s;'
assert old in s
unroll='if(hd_variant()==3){while(n>=64){' + ''.join('uint64_t v'+str(i)+'=*(const volatile alias_word *)(s+'+str(8*i)+');memcpy(d+'+str(8*i)+',&v'+str(i)+',8);' for i in range(8))+'s+=64;d+=64;n-=64;}}'
s=s.replace(old,unroll+old);p.write_text(s)
(OUT/'build/runtime-diagnostic.patch').write_text(call(['diff','-ruN',ROOT/'runtime/shm',src],check=False))

# v3: remove Guest staging payload copy only. Caller owns input until sync return.
p=src/'src/guest.c';s=p.read_text()
s=s.replace('int result;uint64_t rid;', 'int result;uint64_t rid;const void *scatter;')
s=s.replace('job.rid=id;job.result=exchange', 'hd_set_scatter(job.scatter);job.rid=id;job.result=exchange')
s=s.replace('pthread_mutex_lock(&io_lock);work=0;', 'hd_set_scatter(NULL);pthread_mutex_lock(&io_lock);work=0;')
s=s.replace('job.api=api;job.input=input;', 'job.scatter=hd_scatter();job.api=api;job.input=input;')
s=s.replace('if(kind==cudaMemcpyHostToDevice&&n){if(hd_variant()==4)', 'if(kind==cudaMemcpyHostToDevice&&n&&hd_variant()!=5){if(hd_variant()==4)')
s=s.replace('e=flyt_guest_exchange(FLYT_API_RUNTIME_MEMCPY,in,bytes,', 'if(hd_variant()==5&&kind==cudaMemcpyHostToDevice)hd_set_scatter(src);\n    e=flyt_guest_exchange(FLYT_API_RUNTIME_MEMCPY,in,bytes,')
s=s.replace('if(hd&&kind==cudaMemcpyHostToDevice)', 'hd_set_scatter(NULL);if(hd&&kind==cudaMemcpyHostToDevice)')
p.write_text(s)
p=q/'src/queue.c';s=p.read_text();old='if (q->input_bytes) memcpy(c->request_payload, q->input, q->input_bytes);'
assert old in s
s=s.replace(old, 'if(hd_variant()==5&&hd_scatter()){if(q->api_id!=FLYT_API_RUNTIME_MEMCPY||q->input_bytes<48||get((const uint8_t*)q->input,4)!=1||get((const uint8_t*)q->input+4,4)||get((const uint8_t*)q->input+40,8)!=q->input_bytes-48)return FLYT_SHM_BAD_DESCRIPTOR;memcpy(c->request_payload,q->input,48);memcpy(c->request_payload+48,hd_scatter(),q->input_bytes-48);}else '+old)
p.write_text(s)
(OUT/'build/runtime-diagnostic.patch').write_text(call(['diff','-ruN',ROOT/'runtime/shm',src],check=False))

# Final experimental Worker emits a success marker only after CUDA teardown.
p=src/'src/worker.c';s=p.read_text();s=s.replace('return exitcode;', 'fprintf(stderr,"HD_WORKER_EXIT,%d\\n",exitcode);return exitcode;');p.write_text(s)
