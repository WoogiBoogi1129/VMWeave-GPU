/* Diagnostic-only instrumentation; optional state cache assumes one healthy GPU/session. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <pthread.h>
#include <stdatomic.h>
static _Atomic int active;
static _Atomic uint64_t calls[65536],wall[65536],cpu[65536],cache_hits[2],cache_misses[2];
static int (*next_exchange)(uint32_t,const void*,size_t,void*,size_t,size_t*);
static int (*next_get)(int*),(*next_context)(int,unsigned*,int*);
static pthread_once_t once=PTHREAD_ONCE_INIT;
static int cache;
static _Thread_local int device_valid,context_valid,saved_device,saved_active;
static _Thread_local unsigned saved_flags;
static uint64_t now(clockid_t clock){struct timespec t;clock_gettime(clock,&t);return (uint64_t)t.tv_sec*1000000000+t.tv_nsec;}
static void resolve(void){next_exchange=dlsym(RTLD_NEXT,"vmweave_guest_exchange");next_get=dlsym(RTLD_NEXT,"cudaGetDevice");next_context=dlsym(RTLD_NEXT,"cuDevicePrimaryCtxGetState");cache=getenv("VMWEAVE_DIAG_STATE_CACHE")&&strcmp(getenv("VMWEAVE_DIAG_STATE_CACHE"),"1")==0;}
void diag_profile_start(void){for(unsigned i=0;i<65536;i++){calls[i]=wall[i]=cpu[i]=0;}for(int i=0;i<2;i++)cache_hits[i]=cache_misses[i]=0;active=1;}
void diag_profile_stop(void){active=0;FILE*f=fopen("/tmp/perf/client-api-timing.json","w");if(!f)return;fprintf(f,"{\"scope\":\"measurement only; guest vmweave_guest_exchange call boundary\",\"state_cache\":%s,\"cache_hits\":[%lu,%lu],\"cache_misses\":[%lu,%lu],\"apis\":{",cache?"true":"false",(unsigned long)cache_hits[0],(unsigned long)cache_hits[1],(unsigned long)cache_misses[0],(unsigned long)cache_misses[1]);int first=1;for(unsigned i=0;i<65536;i++)if(calls[i]){fprintf(f,"%s\"0x%x\":[%lu,%lu,%lu]",first?"":",",i,(unsigned long)calls[i],(unsigned long)wall[i],(unsigned long)cpu[i]);first=0;}fprintf(f,"}}\n");fclose(f);}
int vmweave_guest_exchange(uint32_t api,const void*in,size_t n,void*out,size_t cap,size_t*got){pthread_once(&once,resolve);int enabled=active;uint64_t w=enabled?now(CLOCK_MONOTONIC):0,c=enabled?now(CLOCK_THREAD_CPUTIME_ID):0;int rc=next_exchange?next_exchange(api,in,n,out,cap,got):999;if(enabled&&api<65536){calls[api]++;wall[api]+=now(CLOCK_MONOTONIC)-w;cpu[api]+=now(CLOCK_THREAD_CPUTIME_ID)-c;}return rc;}
int cudaGetDevice(int*out){pthread_once(&once,resolve);if(cache&&out&&device_valid){*out=saved_device;if(active)cache_hits[0]++;return 0;}if(active)cache_misses[0]++;int rc=next_get?next_get(out):999;if(cache&&!rc&&out&&*out==0){saved_device=*out;device_valid=1;}return rc;}
int cuDevicePrimaryCtxGetState(int dev,unsigned*flags,int*is_active){pthread_once(&once,resolve);if(cache&&dev==0&&flags&&is_active&&context_valid){*flags=saved_flags;*is_active=saved_active;if(active)cache_hits[1]++;return 0;}if(active)cache_misses[1]++;int rc=next_context?next_context(dev,flags,is_active):999;if(cache&&!rc&&dev==0&&flags&&is_active&&*is_active){saved_flags=*flags;saved_active=*is_active;context_valid=1;}return rc;}
