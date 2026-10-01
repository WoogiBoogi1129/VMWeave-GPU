#define _GNU_SOURCE
#include <assert.h>
#include <stdio.h>
#include <sys/mman.h>
#include "../../runtime/shm/shm-queue/src/queue.c"
int main(void){
 size_t page=4096;unsigned char *p=mmap(NULL,page*3,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
 assert(p!=MAP_FAILED&&!mprotect(p+page,page,PROT_READ|PROT_WRITE));
 for(size_t i=0;i<page;i++)p[page+i]=(unsigned char)(i*17);
 unsigned char out[4098];
 for(size_t n=0;n<=4096;n++){
  memset(out,0xcc,sizeof(out));payload_snapshot(out+1,p+2*page-n,n);
  assert(!memcmp(out+1,p+2*page-n,n)&&out[0]==0xcc&&out[n+1]==0xcc);
 }
 munmap(p,page*3);
 struct flyt_shm_layout l={.region_bytes=1048576,.session_count=1};memset(l.allocation_id,1,16);memset(l.channel_generation,2,16);memset(l.slots[0].session_id,3,16);
 l.slots[0].request_ring=(struct flyt_shm_ring_layout){4096,64};l.slots[0].response_ring=(struct flyt_shm_ring_layout){16384,64};
 l.slots[0].request_payload=(struct flyt_shm_arena){32768,4096};l.slots[0].response_payload=(struct flyt_shm_arena){36864,4096};
 p=mmap(NULL,l.region_bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);assert(p!=MAP_FAILED);assert(!flyt_shm_format(p,l.region_bytes,&l));
 struct flyt_shm_channel *g,*w;assert(!flyt_shm_open(p,l.region_bytes,&l,0,FLYT_SHM_GUEST,1,&g));assert(!flyt_shm_open(p,l.region_bytes,&l,0,FLYT_SHM_WORKER,1,&w));
 unsigned char input[65],output[65];memset(input,0x5a,65);
 struct flyt_shm_request q={.request_id=1,.api_id=1,.payload_schema=1,.input=input,.input_bytes=65},taken;
 q.identity=g->identity;assert(!flyt_shm_submit(g,&q));assert(flyt_shm_submit(g,&q)==FLYT_SHM_QUEUE_FULL);assert(!flyt_shm_worker_take(w,&taken));
 memset(p+32768,0x77,65);assert(!memcmp(taken.input,input,65));
 struct flyt_shm_response r={.output=(void*)taken.input,.output_capacity=65,.output_bytes=65};assert(!flyt_shm_worker_respond(w,&r));flyt_shm_request_release(&taken);
 r=(struct flyt_shm_response){.output=output,.output_capacity=64};assert(flyt_shm_try_receive(g,1,&r)==FLYT_SHM_BAD_DESCRIPTOR&&r.output_bytes==65);
 r.output_capacity=65;assert(!flyt_shm_try_receive(g,1,&r)&&!memcmp(input,output,65));
 q.request_id=2;assert(!flyt_shm_submit(g,&q));
 /* Corrupted peer payload offset must fail before touching a mapping. */
 put(p+4096+128+128+64,UINT64_MAX,8);assert(flyt_shm_worker_take(w,&taken)==FLYT_SHM_BAD_DESCRIPTOR);
 struct timespec delay={0,2000000};nanosleep(&delay,NULL);assert(flyt_shm_receive(g,2,&r)==FLYT_SHM_EXECUTION_UNKNOWN);
 flyt_shm_close(g);flyt_shm_close(w);munmap(p,l.region_bytes);
 puts("PASS: guarded payload tails, private snapshot, single pending, receive retry, corrupted offset and timeout");
}
