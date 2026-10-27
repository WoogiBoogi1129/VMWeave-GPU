#define _GNU_SOURCE
#include <assert.h>
#include <stdio.h>
#include <sys/mman.h>
#include "../source/runtime/shm/shm-queue/src/queue.c"
int main(void){
 struct vmweave_shm_layout l={.region_bytes=1048576,.session_count=1};
 memset(l.allocation_id,1,16);memset(l.channel_generation,2,16);memset(l.slots[0].session_id,3,16);
 l.slots[0].request_ring=(struct vmweave_shm_ring_layout){4096,64};l.slots[0].response_ring=(struct vmweave_shm_ring_layout){16384,64};
 l.slots[0].request_payload=(struct vmweave_shm_arena){32768,4096};l.slots[0].response_payload=(struct vmweave_shm_arena){36864,4096};
 void *m=mmap(NULL,l.region_bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);assert(m!=MAP_FAILED);
 assert(!vmweave_shm_format(m,l.region_bytes,&l));struct vmweave_shm_channel *g,*w;
 assert(!vmweave_shm_open(m,l.region_bytes,&l,0,VMWEAVE_SHM_GUEST,1000,&g));assert(!vmweave_shm_open(m,l.region_bytes,&l,0,VMWEAVE_SHM_WORKER,1000,&w));
 unsigned char scratch[4098],out[4096],a[48],b[4048];memset(a,0x5a,sizeof(a));memset(b,0xa5,sizeof(b));
 struct vmweave_shm_request q={.identity=g->identity,.request_id=1,.api_id=1,.payload_schema=1,.input_bytes=4096},taken;
 struct vmweave_shm_part parts[2]={{a,48},{b,4048}};
 parts[1].bytes=SIZE_MAX;assert(vmweave_shm_submit_parts(g,&q,parts,2)==VMWEAVE_SHM_BAD_DESCRIPTOR&&!g->pending);parts[1].bytes=4048;
 assert(!vmweave_shm_submit_parts(g,&q,parts,2));
 assert(vmweave_shm_worker_take_into(w,&taken,scratch,4095)==VMWEAVE_SHM_BAD_DESCRIPTOR&&!w->pending);
 memset(scratch,0xcc,sizeof(scratch));assert(!vmweave_shm_worker_take_into(w,&taken,scratch+1,4096));
 assert(taken.input==scratch+1&&!memcmp(taken.input,a,48)&&!memcmp(taken.input+48,b,4048));
 assert(scratch[0]==0xcc&&scratch[4097]==0xcc);
 memset((char*)m+32768,0,4096);assert(taken.input[0]==0x5a);
 struct vmweave_shm_response r={.output=(void*)taken.input,.output_capacity=4096,.output_bytes=4096};assert(!vmweave_shm_worker_respond(w,&r));
 vmweave_shm_request_clear_borrowed(&taken);assert(!taken.input&&scratch[1]==0x5a);
 r=(struct vmweave_shm_response){.output=out,.output_capacity=4095};assert(vmweave_shm_try_receive(g,1,&r)==VMWEAVE_SHM_BAD_DESCRIPTOR);
 r.output_capacity=4096;assert(!vmweave_shm_try_receive(g,1,&r));assert(!memcmp(out,a,48)&&!memcmp(out+48,b,4048));
 q.request_id=2;q.input=a;q.input_bytes=48;assert(!vmweave_shm_submit(g,&q));assert(!vmweave_shm_worker_take(w,&taken));
 assert(taken.input!=scratch+1);r=(struct vmweave_shm_response){0};assert(!vmweave_shm_worker_respond(w,&r));vmweave_shm_request_release(&taken);
 assert(!vmweave_shm_try_receive(g,2,&r));vmweave_shm_close(g);vmweave_shm_close(w);munmap(m,l.region_bytes);
 puts("PASS gather, bounds, nonconsumption, borrowed ownership, legacy release, receive retry");
}
