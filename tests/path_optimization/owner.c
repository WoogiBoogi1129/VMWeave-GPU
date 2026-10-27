#define _POSIX_C_SOURCE 200809L
#include "../../runtime/shm/src/owner.c"
#include <assert.h>
#include <stdio.h>
#include <sys/wait.h>
/* Real native owner with CPU-only mapping/queue mocks. No CUDA library loaded. */
static unsigned submissions,closes;static uint32_t last_api;static int reject;
int vmweave_layout_read(const char *path,struct vmweave_shm_layout *l){(void)path;memset(l,0,sizeof(*l));l->session_count=1;l->slots[0].request_payload.bytes=4096;return 0;}
int vmweave_map_guest(const char *bdf,const struct vmweave_shm_layout *l,struct vmweave_mapping *m){(void)bdf;(void)l;m->address=malloc(4096);m->bytes=4096;return !m->address;}
void vmweave_unmap(struct vmweave_mapping *m){free(m->address);m->address=NULL;}
int vmweave_shm_open(void *p,size_t bytes,const struct vmweave_shm_layout *l,uint32_t slot,enum vmweave_shm_role role,uint32_t timeout,struct vmweave_shm_channel **c){(void)bytes;(void)l;(void)slot;(void)role;(void)timeout;*c=p;return 0;}
void vmweave_shm_close(struct vmweave_shm_channel *c){(void)c;++closes;}
void vmweave_shm_abort(struct vmweave_shm_channel *c){(void)c;}
size_t vmweave_shm_response_capacity(const struct vmweave_shm_channel *c){(void)c;return 4096;}
int vmweave_shm_submit_parts(struct vmweave_shm_channel *c,const struct vmweave_shm_request *q,const struct vmweave_shm_part *p,size_t n){(void)c;assert(n==2&&p[0].bytes+p[1].bytes==q->input_bytes);++submissions;last_api=q->api_id;return 0;}
int vmweave_shm_receive(struct vmweave_shm_channel *c,uint64_t id,struct vmweave_shm_response *r){(void)c;(void)id;r->output_bytes=0;r->result_domain=3;r->transport_status=reject;return 0;}
static void *wrong_thread(void *arg){size_t got=123;assert(vmweave_owner_exchange(arg,3,NULL,0,NULL,0,NULL,0,&got)==999&&!got);return NULL;}
int main(void){
 unsetenv("VMWEAVE_BROKER_SOCKET");unsetenv("FLYT_BROKER_SOCKET");setenv("VMWEAVE_LAYOUT","mock",1);setenv("VMWEAVE_IVSHMEM_BDF","mock",1);setenv("VMWEAVE_SLOT","0",1);
 struct vmweave_owner *o;assert(!vmweave_owner_open(&o)&&last_api==1);size_t a,b,got;
 assert(!vmweave_owner_limits(o,&a,&b)&&a==4096&&b==4096);
 pthread_t t;assert(!pthread_create(&t,NULL,wrong_thread,o)&&!pthread_join(t,NULL));assert(submissions==1);
 pid_t child=fork();assert(child>=0);
 if(!child){wrong_thread(o);_exit(0);}
 int status;assert(waitpid(child,&status,0)==child&&WIFEXITED(status)&&!WEXITSTATUS(status));
 assert(vmweave_owner_exchange(o,6,"x",1,"x",4096,NULL,0,&got)==1&&submissions==1);
 reject=VMWEAVE_SHM_UNSUPPORTED_API;assert(vmweave_owner_exchange(o,99,NULL,0,NULL,0,NULL,0,&got)==801&&!o->failed);
 reject=VMWEAVE_SHM_BAD_DESCRIPTOR;assert(vmweave_owner_exchange(o,99,NULL,0,NULL,0,NULL,0,&got)==999&&o->failed);
 unsigned before=submissions;assert(vmweave_owner_exchange(o,99,NULL,0,NULL,0,NULL,0,&got)==999&&submissions==before);
 assert(!vmweave_owner_close(o)&&closes==1);puts("PASS owner thread affinity, sizes, unsupported, sticky failure, cleanup");
}
