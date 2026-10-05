#define _GNU_SOURCE
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "flyt_shm_queue.h"
#include "hd_diag.h"
static void put(unsigned char *p,uint64_t x,unsigned n){for(unsigned i=0;i<n;i++)p[i]=(unsigned char)(x>>(i*8));}
int main(void){
 struct flyt_shm_layout l={.region_bytes=1048576,.session_count=1};memset(l.allocation_id,1,16);memset(l.channel_generation,2,16);memset(l.slots[0].session_id,3,16);
 l.slots[0].request_ring=(struct flyt_shm_ring_layout){4096,64};l.slots[0].response_ring=(struct flyt_shm_ring_layout){16384,64};
 l.slots[0].request_payload=(struct flyt_shm_arena){32768,4096};l.slots[0].response_payload=(struct flyt_shm_arena){36864,4096};
 unsigned char *shared=calloc(1,l.region_bytes);assert(shared);assert(!flyt_shm_format(shared,l.region_bytes,&l));struct flyt_shm_channel *g,*w;
 assert(!flyt_shm_open(shared,l.region_bytes,&l,0,FLYT_SHM_GUEST,1000,&g));assert(!flyt_shm_open(shared,l.region_bytes,&l,0,FLYT_SHM_WORKER,1000,&w));
 unsigned char header[48]={0},payload[65],out[1];memset(payload,0x5a,sizeof(payload));put(header,1,4);put(header+40,sizeof(payload),8);
 struct flyt_shm_request q={.request_id=1,.api_id=FLYT_API_RUNTIME_MEMCPY,.payload_schema=1,.input=header,.input_bytes=sizeof(header)+sizeof(payload)},taken;
 memcpy(q.identity.channel_generation,l.channel_generation,16);memcpy(q.identity.session_id,l.slots[0].session_id,16);
 hd_set_scatter(payload);put(header+40,66,8);assert(flyt_shm_submit(g,&q)==FLYT_SHM_BAD_DESCRIPTOR);put(header+40,65,8);
 q.api_id=FLYT_API_RUNTIME_MALLOC;assert(flyt_shm_submit(g,&q)==FLYT_SHM_BAD_DESCRIPTOR);q.api_id=FLYT_API_RUNTIME_MEMCPY;
 assert(!flyt_shm_submit(g,&q));hd_set_scatter(NULL);memset(payload,0xa5,sizeof(payload));assert(!flyt_shm_worker_take(w,&taken));
 assert(taken.input_bytes==113&&!memcmp(taken.input,header,48));for(size_t i=48;i<113;i++)assert(((unsigned char*)taken.input)[i]==0x5a);
 memset(shared+32768,0xcc,113);for(size_t i=48;i<113;i++)assert(((unsigned char*)taken.input)[i]==0x5a);
 struct flyt_shm_response r={.output=out,.output_capacity=1};assert(!flyt_shm_worker_respond(w,&r));flyt_shm_request_release(&taken);assert(!flyt_shm_try_receive(g,1,&r));
 flyt_shm_close(g);flyt_shm_close(w);hd_cleanup();uint64_t pending=hd_now();hd_dump("scatter-test");assert(hd_now()==0);hd_record(10,0,0,pending);hd_pack_record(0,0,pending,pending+1);free(shared);puts("PASS: 48-byte header-only input, exact payload span, length/API rejection, user-input lifetime, private Worker snapshot");
}
