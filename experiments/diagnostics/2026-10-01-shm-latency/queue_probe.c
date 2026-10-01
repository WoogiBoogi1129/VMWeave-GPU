/* Host-only component diagnostic, linked to the original measured Guest library.
 * No VM, CUDA, HAMi, BAR mapping or Guest I/O-thread handoff is exercised.
 */
#define _GNU_SOURCE
#include "flyt_shm_queue.h"
#include <pthread.h>
#include <stdatomic.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#define OK(x) do { int e=(x); if(e){fprintf(stderr,"%s: %d\n",#x,e);exit(2);} } while(0)
static struct flyt_shm_layout layout;
static void *mapping;
static pthread_barrier_t barrier;
static atomic_int stopping;
static size_t input_bytes,output_bytes;
static int guest_spin,worker_spin;
static unsigned char *input,*expected;
static double now(clockid_t c){struct timespec t;clock_gettime(c,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static void pin(int cpu){cpu_set_t s;CPU_ZERO(&s);CPU_SET(cpu,&s);OK(pthread_setaffinity_np(pthread_self(),sizeof(s),&s));}
static void pause_poll(void){struct timespec t={0,1000000};nanosleep(&t,NULL);}
static void *worker(void *unused){
 (void)unused;pin(50);struct flyt_shm_channel *c;OK(flyt_shm_open(mapping,layout.region_bytes,&layout,0,FLYT_SHM_WORKER,30000,&c));
 pthread_barrier_wait(&barrier);
 while(!atomic_load(&stopping)){
  struct flyt_shm_request q={0};int e=flyt_shm_worker_take(c,&q);
  if(e==FLYT_SHM_AGAIN){if(!worker_spin)pause_poll();else __asm__ volatile("pause");continue;}OK(e);
  if(input_bytes && (((const unsigned char*)q.input)[0]!=0x5a || ((const unsigned char*)q.input)[input_bytes-1]!=0x5a))exit(3);
  if(q.api_id==0x7ffe && input_bytes && memcmp(q.input,input,input_bytes))exit(3);
  struct flyt_shm_response r={.output=expected,.output_capacity=output_bytes,.output_bytes=output_bytes};
  OK(flyt_shm_worker_respond(c,&r));flyt_shm_request_release(&q);
 }
 flyt_shm_close(c);return NULL;
}
static int cmp(const void *a,const void *b){double x=*(const double*)a,y=*(const double*)b;return (x>y)-(x<y);}
int main(int argc,char **argv){
 if(argc!=6)return 1;
 const char *policy=argv[1];guest_spin=!strcmp(policy,"guest_spin")||!strcmp(policy,"both_spin");worker_spin=!strcmp(policy,"worker_spin")||!strcmp(policy,"both_spin");
 if(strcmp(policy,"stock")&&!guest_spin&&!worker_spin)return 1;
 input_bytes=strtoul(argv[2],NULL,10);output_bytes=strtoul(argv[3],NULL,10);double seconds=atof(argv[4]);
 if(input_bytes>16777216||output_bytes>16777216||seconds<=0||seconds>10)return 1;
 layout.region_bytes=36*1024*1024;layout.session_count=1;
 memset(layout.allocation_id,1,16);memset(layout.channel_generation,2,16);memset(layout.slots[0].session_id,3,16);
 layout.slots[0].request_ring=(struct flyt_shm_ring_layout){4096,64};layout.slots[0].response_ring=(struct flyt_shm_ring_layout){16384,64};
 layout.slots[0].request_payload=(struct flyt_shm_arena){32768,16777216};layout.slots[0].response_payload=(struct flyt_shm_arena){32768+16777216,16777216};
 pin(48);mapping=mmap(NULL,layout.region_bytes,PROT_READ|PROT_WRITE,MAP_SHARED|MAP_ANONYMOUS,-1,0);if(mapping==MAP_FAILED)return 2;
 OK(flyt_shm_format(mapping,layout.region_bytes,&layout));
 input=malloc(input_bytes?input_bytes:1);expected=malloc(output_bytes?output_bytes:1);unsigned char *out=malloc(output_bytes?output_bytes:1);
 if(!input||!expected||!out)return 2;
 memset(input,0x5a,input_bytes);memset(expected,0x5a,output_bytes);
 struct flyt_shm_channel *c;OK(flyt_shm_open(mapping,layout.region_bytes,&layout,0,FLYT_SHM_GUEST,30000,&c));
 OK(pthread_barrier_init(&barrier,NULL,2));pthread_t thread;OK(pthread_create(&thread,NULL,worker,NULL));pthread_barrier_wait(&barrier);
 size_t count=0,capacity=2000000;double *lat=malloc(capacity*sizeof(double)),start=0,cpu=0,finish=0,used=0;uint64_t id=1;
 if(!lat)return 2;
 for(;;id++){
  if(id==201){start=now(CLOCK_MONOTONIC);cpu=now(CLOCK_PROCESS_CPUTIME_ID);}
  int final=count && now(CLOCK_MONOTONIC)-start>=seconds;
  if(final){finish=now(CLOCK_MONOTONIC);used=now(CLOCK_PROCESS_CPUTIME_ID)-cpu;}
  struct flyt_shm_request q={.request_id=id,.api_id=final?0x7ffe:0x7ffd,.payload_schema=1,.input=input,.input_bytes=input_bytes};
  memcpy(q.identity.channel_generation,layout.channel_generation,16);memcpy(q.identity.session_id,layout.slots[0].session_id,16);
  struct flyt_shm_response r={.output=out,.output_capacity=output_bytes};double begin=now(CLOCK_MONOTONIC);OK(flyt_shm_submit(c,&q));
  if(!guest_spin)OK(flyt_shm_receive(c,id,&r));else{int e;while((e=flyt_shm_try_receive(c,id,&r))==FLYT_SHM_AGAIN)__asm__ volatile("pause");OK(e);}
  double elapsed=now(CLOCK_MONOTONIC)-begin;
  if(r.output_bytes!=output_bytes||r.transport_status||r.api_result)return 3;
  if(output_bytes && (out[0]!=0x5a||out[output_bytes-1]!=0x5a))return 3;
  if(final){if(memcmp(out,expected,output_bytes))return 3;break;}
  if(id>=201){if(count==capacity)return 4;lat[count++]=elapsed;}
 }
 atomic_store(&stopping,1);OK(pthread_join(thread,NULL));flyt_shm_close(c);
 FILE *f=fopen(argv[5],"w");if(!f)return 2;fprintf(f,"sample,seconds\n");double sum=0;
 for(size_t i=0;i<count;i++){fprintf(f,"%zu,%.9f\n",i,lat[i]);sum+=lat[i];}fclose(f);qsort(lat,count,sizeof(double),cmp);
 printf("{\"policy\":\"%s\",\"input_bytes\":%zu,\"output_bytes\":%zu,\"count\":%zu,\"mean_us\":%.6f,\"p50_us\":%.6f,\"p95_us\":%.6f,\"cpu_cores\":%.6f,\"duration_s\":%.6f,\"final_payload_check\":\"PASS\"}\n",policy,input_bytes,output_bytes,count,sum/count*1e6,lat[count/2]*1e6,lat[(count-1)*95/100]*1e6,used/(finish-start),finish-start);
 free(lat);free(input);free(expected);free(out);munmap(mapping,layout.region_bytes);return 0;
}
