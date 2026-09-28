#ifndef FLYT_TRACE_H
#define FLYT_TRACE_H
/* Opt-in endpoint observations, not wire fields or cross-machine latency clocks.
 * A publication event is written only after the queue operation succeeds.
 * No payload contents or process/device virtual addresses are logged.
 */
#include "flyt_wire.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
static inline void flyt_trace(const char *role,const char *event,const uint8_t allocation[16],
                              const struct flyt_shm_request *q,const struct flyt_shm_response *r){
    const char *enabled=getenv("FLYT_TRACE_REQUESTS");
    if(!enabled||strcmp(enabled,"1"))return;
    char a[33],g[33],s[33];
    for(unsigned i=0;i<16;i++){
        snprintf(a+2*i,3,"%02x",allocation[i]);
        snprintf(g+2*i,3,"%02x",q->identity.channel_generation[i]);
        snprintf(s+2*i,3,"%02x",q->identity.session_id[i]);
    }
    struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);
    char result[192]="\"transport_status\":null,\"result_domain\":null,\"api_result\":null,\"output_bytes\":null";
    if(r)snprintf(result,sizeof(result),"\"transport_status\":%u,\"result_domain\":%u,\"api_result\":%u,\"output_bytes\":%zu",
                  r->transport_status,r->result_domain,r->api_result,r->output_bytes);
    char semantic[256]="";
    if(q->api_id==FLYT_API_RUNTIME_MALLOC&&q->input_bytes==8)
        snprintf(semantic,sizeof(semantic),",\"requested_bytes\":%" PRIu64 ",\"allocation_handle\":%" PRIu64,
                 flyt_get(q->input,8),r&&!r->transport_status&&!r->api_result&&r->output_bytes==8?flyt_get(r->output,8):0);
    if(q->api_id==FLYT_API_RUNTIME_FREE&&q->input_bytes==8)
        snprintf(semantic,sizeof(semantic),",\"allocation_handle\":%" PRIu64,flyt_get(q->input,8));
    if(q->api_id==FLYT_API_RUNTIME_MEMCPY&&q->input_bytes>=48)
        snprintf(semantic,sizeof(semantic),",\"copy_direction\":%u,\"copy_bytes\":%" PRIu64
                 ",\"dst_handle\":%" PRIu64 ",\"src_handle\":%" PRIu64,
                 (unsigned)flyt_get(q->input,4),flyt_get(q->input+40,8),flyt_get(q->input+8,8),flyt_get(q->input+24,8));
    fprintf(stderr,"FLYT_TRACE {\"version\":1,\"role\":\"%s\",\"event\":\"%s\",\"pid\":%ld,\"monotonic_ns\":%" PRIu64
            ",\"allocation\":\"%s\",\"generation\":\"%s\",\"session_id\":\"%s\",\"request_id\":%" PRIu64
            ",\"api_id\":%u,\"input_bytes\":%zu,%s%s}\n",
            role,event,(long)getpid(),(uint64_t)t.tv_sec*UINT64_C(1000000000)+(uint64_t)t.tv_nsec,
            a,g,s,q->request_id,q->api_id,q->input_bytes,result,semantic);
}
#endif
