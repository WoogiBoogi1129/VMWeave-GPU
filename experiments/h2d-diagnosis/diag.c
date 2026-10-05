/* Experiment-only: bounded in-memory records; no timed-loop file writes.
 * Monotonic timestamps remain within their clock domain; IDs join endpoints. */
#define _GNU_SOURCE
#include "hd_diag.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <dlfcn.h>
#include <stdint.h>
struct rec {uint64_t id,bytes,end,ns;unsigned stage;};
static _Thread_local struct rec *rows;
static _Thread_local size_t count,dropped;
static _Thread_local uint64_t current;
static _Thread_local int init,enabled,variant;
static _Thread_local void *buffer;
static _Thread_local size_t capacity;
#define CAP 1500000
static void setup(void){if(init)return;init=1;const char *v=getenv("HD_VARIANT");variant=v&&!strcmp(v,"reuse")?1:v&&!strcmp(v,"pinned")?2:v&&!strcmp(v,"unroll")?3:v&&!strcmp(v,"chunk")?4:v&&!strcmp(v,"direct")?5:0;const char *e=getenv("HD_METRICS");enabled=e&&!strcmp(e,"1");if(enabled){rows=calloc(CAP,sizeof(*rows));if(!rows)abort();}}
uint64_t hd_now(void){setup();if(!enabled)return 0;struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint64_t)t.tv_sec*1000000000+t.tv_nsec;}
void hd_record(unsigned stage,uint64_t id,size_t bytes,uint64_t start){if(!start||!enabled)return;uint64_t end=hd_now();if(count==CAP){dropped++;return;}rows[count++]=(struct rec){id,bytes,end,end-start,stage};}
void hd_set_id(uint64_t id){current=id;}
uint64_t hd_id(void){return current;}
void hd_dump(const char *role){if(!enabled)return;enabled=0;fprintf(stderr,"HD_BEGIN,%s,%zu,%zu\n",role,count,dropped);for(size_t i=0;i<count;i++){struct rec *r=rows+i;fprintf(stderr,"HD,%s,%u,%lu,%lu,%lu,%lu\n",role,r->stage,r->id,r->bytes,r->end,r->ns);}fprintf(stderr,"HD_END,%s\n",role);free(rows);rows=NULL;count=0;}
void *hd_alloc(size_t n){setup();if(variant!=1&&variant!=2)return malloc(n);if(n<=capacity)return buffer;if(buffer){if(variant==2){int(*f)(void*)=dlsym(RTLD_DEFAULT,"cudaFreeHost");if(!f||f(buffer))abort();}else free(buffer);}buffer=NULL;capacity=0;if(variant==2){int(*f)(void**,size_t,unsigned)=dlsym(RTLD_DEFAULT,"cudaHostAlloc");if(!f||f(&buffer,n,0))return NULL;}else buffer=malloc(n);if(buffer)capacity=n;return buffer;}
void hd_free(void *p){if(p!=buffer)free(p);}
void hd_cleanup(void){if(buffer){if(variant==2){int(*f)(void*)=dlsym(RTLD_DEFAULT,"cudaFreeHost");if(!f||f(buffer))abort();}else free(buffer);}buffer=NULL;capacity=0;}

int hd_variant(void){setup();return variant;}

static _Thread_local const void *scatter_input;
void hd_set_scatter(const void *p){scatter_input=p;}
const void *hd_scatter(void){return scatter_input;}

void hd_pack_record(uint64_t id,size_t bytes,uint64_t start,uint64_t end){if(!start||!enabled)return;if(count==CAP){dropped++;return;}rows[count++]=(struct rec){id,bytes,end,end-start,1};}
