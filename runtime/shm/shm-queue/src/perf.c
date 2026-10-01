#define _POSIX_C_SOURCE 200809L
#include "flyt_perf.h"
#include <errno.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
static pthread_once_t once=PTHREAD_ONCE_INIT;
static int enabled, optimized, bounded;
static unsigned spin_us=0, sleep_us=50;
struct measure { uint64_t calls,ns,bytes; };
static _Thread_local struct measure measures[FLYT_PERF_STAGES];
static _Thread_local uint64_t spin_calls,sleep_calls,sleep_ns;
static unsigned setting(const char *key,unsigned fallback,unsigned maximum){
    const char *s=getenv(key);char *end;unsigned long v;
    if(!s||!*s)return fallback;
    errno=0;v=strtoul(s,&end,10);
    return errno||*end||v>maximum?fallback:(unsigned)v;
}
static void configure(void){
    const char *s=getenv("FLYT_WAIT_MODE");
    bounded=!s||!strcmp(s,"bounded");
    s=getenv("FLYT_COPY_MODE");optimized=!s||!strcmp(s,"optimized");
    s=getenv("FLYT_METRICS");enabled=s&&!strcmp(s,"1");
    spin_us=setting("FLYT_SPIN_US",0,1000);
    sleep_us=setting("FLYT_SLEEP_US",50,1000);if(!sleep_us)sleep_us=50;
}
int flyt_perf_enabled(void){pthread_once(&once,configure);return enabled;}
int flyt_copy_optimized(void){pthread_once(&once,configure);return optimized;}
uint64_t flyt_perf_now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint64_t)t.tv_sec*1000000000+t.tv_nsec;}
void flyt_perf_add(enum flyt_perf_stage stage,uint64_t start,size_t bytes){
    if(!enabled||!start)return;
    measures[stage].calls++;measures[stage].ns+=flyt_perf_now()-start;measures[stage].bytes+=bytes;
}
void flyt_perf_dump(const char *role){
    static const char *names[]={"submit","take","respond","receive","dispatch","exchange"};
    if(!flyt_perf_enabled())return;
    for(unsigned i=0;i<FLYT_PERF_STAGES;i++)if(measures[i].calls){
        fprintf(stderr,"{\"event\":\"FLYT_METRIC\",\"role\":\"%s\",\"stage\":\"%s\",\"calls\":%llu,\"ns\":%llu,\"bytes\":%llu}\n",role,names[i],(unsigned long long)measures[i].calls,(unsigned long long)measures[i].ns,(unsigned long long)measures[i].bytes);
    }
    fprintf(stderr,"{\"event\":\"FLYT_WAIT\",\"role\":\"%s\",\"mode\":\"%s\",\"copy\":\"%s\",\"spin_us\":%u,\"sleep_us\":%u,\"spin_calls\":%llu,\"sleep_calls\":%llu,\"sleep_ns\":%llu}\n",role,bounded?"bounded":"legacy",optimized?"optimized":"legacy",spin_us,sleep_us,(unsigned long long)spin_calls,(unsigned long long)sleep_calls,(unsigned long long)sleep_ns);
    memset(measures,0,sizeof(measures));spin_calls=sleep_calls=sleep_ns=0;
}
int flyt_wait_pause(struct flyt_wait *w){
    pthread_once(&once,configure);
    uint64_t now=0;
    if(bounded){
        now=flyt_perf_now();if(!w->started)w->started=now;
        if(now-w->started<(uint64_t)spin_us*1000){
            __asm__ volatile("pause");if(enabled)spin_calls++;return 0;
        }
    }
    /* Back off after 10ms without work. Do not keep an idle Worker hot. */
    unsigned delay=bounded&&now-w->started<10000000?sleep_us:1000;
    struct timespec t={0,(long)delay*1000};uint64_t start=enabled?flyt_perf_now():0;
    int rc=nanosleep(&t,NULL);int saved=errno;
    if(enabled){sleep_calls++;sleep_ns+=flyt_perf_now()-start;}
    w->sleeps++;return rc&&saved!=EINTR?-1:0;
}
