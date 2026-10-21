#define _POSIX_C_SOURCE 200809L
#include "vmweave_wire.h"
#include "vmweave_async.h"
#include "vmweave_compat.h"
#include "vmweave_torch.h"
#include "vmweave_trace.h"
#include "vmweave_perf.h"
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
static volatile sig_atomic_t stopping;
static void stop(int x){(void)x;stopping=1;}
int main(int argc,char **argv){
    struct vmweave_shm_layout layout;struct vmweave_mapping mapping={0};struct vmweave_shm_channel *channel=NULL;
    struct vmweave_cuda_runtime *runtime=NULL;struct vmweave_cuda_session session={0};uint32_t error=0;
    char layout_path[512],backing[512],ready[128];int exitcode=1,hello=0;unsigned slot;
    if(argc!=3)return 2;char *end;unsigned long parsed=strtoul(argv[2],&end,10);
    if(*end||parsed>=32)return 2;slot=(unsigned)parsed;
    if(snprintf(layout_path,sizeof(layout_path),"%s/layout.bin",argv[1])>=(int)sizeof(layout_path)||snprintf(backing,sizeof(backing),"%s/channel",argv[1])>=(int)sizeof(backing))return 2;
    if(vmweave_layout_read(layout_path,&layout)||slot>=layout.session_count||vmweave_map_file(backing,&layout,&mapping))return 3;
    if(vmweave_shm_open(mapping.address,mapping.bytes,&layout,slot,VMWEAVE_SHM_WORKER,30000,&channel))goto done;
    if(vmweave_cuda_runtime_open(&runtime,&error)||vmweave_cuda_exec_create(vmweave_cuda_runtime_backend(),runtime,&session.exec))goto done;
    signal(SIGTERM,stop);signal(SIGINT,stop);
    size_t capacity=vmweave_shm_response_capacity(channel);uint8_t *output=malloc(capacity);
    if(!output)goto done;
    snprintf(ready,sizeof(ready),"/tmp/vmweave-slot-%u-mapped",slot);FILE *f=fopen(ready,"wx");if(!f){free(output);goto done;}fclose(f);
    struct timespec last,now;clock_gettime(CLOCK_MONOTONIC,&last);
    struct vmweave_wait idle={0};
    while(!stopping){
        if(vmweave_cuda_exec_check(session.exec)!=VMWEAVE_SHM_OK)break;
        clock_gettime(CLOCK_MONOTONIC,&now);
        if(now.tv_sec-last.tv_sec>(hello?60:600))break;
        if(vmweave_async_reap())break;
        struct vmweave_shm_request q={0};int rc=vmweave_shm_worker_take(channel,&q);
        if(rc==VMWEAVE_SHM_AGAIN){if(vmweave_wait_pause(&idle))break;continue;}
        if(rc)break;
        memset(&idle,0,sizeof(idle));
        uint64_t measured=vmweave_perf_enabled()?vmweave_perf_now():0;
        vmweave_trace("worker","take",layout.allocation_id,&q,NULL);
        clock_gettime(CLOCK_MONOTONIC,&last);
        struct vmweave_shm_response r={.output=output,.output_capacity=capacity};
        if(q.api_id==VMWEAVE_HELLO&&!hello&&q.payload_schema==1&&!q.input_bytes){hello=1;}
        else if(!hello){r.transport_status=VMWEAVE_SHM_CHANNEL_CLOSED;stopping=1;}
        else if((q.api_id==VMWEAVE_HEARTBEAT||q.api_id==VMWEAVE_GOODBYE)&&q.payload_schema==1&&!q.input_bytes){
            if(q.api_id==VMWEAVE_GOODBYE){stopping=1;exitcode=0;}
        }else if(q.api_id==VMWEAVE_HELLO){r.transport_status=VMWEAVE_SHM_BAD_DESCRIPTOR;stopping=1;}
        else if((rc=vmweave_cuda_exec_check(session.exec))!=VMWEAVE_SHM_OK){r.transport_status=(uint32_t)rc;}
        else if(q.api_id>=0x3000){if(vmweave_compat_dispatch(&session,&q,&r)){vmweave_shm_request_release(&q);break;}}
        else if(q.api_id>=0x2100&&q.api_id!=VMWEAVE_STREAM_PRIORITY_CREATE){if(vmweave_torch_dispatch(&session,&q,&r)){vmweave_shm_request_release(&q);break;}}
        else if(q.api_id>=0x2000){if(vmweave_async_dispatch(&session,&q,&r)){vmweave_shm_request_release(&q);break;}}
        else if(vmweave_cuda_dispatch(&session,&q,&r)){vmweave_shm_request_release(&q);break;}
        vmweave_perf_add(VMWEAVE_PERF_DISPATCH,measured,q.input_bytes);
        rc=vmweave_shm_worker_respond(channel,&r);
        if(!rc)vmweave_trace("worker","respond",layout.allocation_id,&q,&r);
        vmweave_shm_request_release(&q);if(rc)break;
        if(hello){char path[128];snprintf(path,sizeof(path),"/tmp/vmweave-slot-%u-guest",slot);FILE *g=fopen(path,"a");if(g)fclose(g);}
    }
    unlink(ready);char guest_marker[128];snprintf(guest_marker,sizeof(guest_marker),"/tmp/vmweave-slot-%u-guest",slot);unlink(guest_marker);free(output);
done:
    /* A poisoned execution context must not enter CUDA again through async
     * polling or resource destructors. Process exit owns uncertain GPU state. */
    if(session.exec&&vmweave_cuda_exec_check(session.exec)==VMWEAVE_SHM_CHANNEL_CLOSED){
        vmweave_shm_close(channel);vmweave_unmap(&mapping);return 1;
    }
    if(session.exec&&vmweave_compat_close())return 1;
    if(session.exec&&vmweave_async_close())return 1; /* process exit releases uncertain CUDA state */
    if(session.exec&&vmweave_cuda_exec_destroy(&session.exec,&error))exitcode=1;
    if(!session.exec)vmweave_cuda_runtime_close(runtime);
    vmweave_shm_close(channel);vmweave_unmap(&mapping);return exitcode;
}
