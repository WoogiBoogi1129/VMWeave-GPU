#include "../source/runtime/shm/src/session_ipc.c"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/wait.h>

static void bad_request(unsigned offset,uint64_t value,unsigned width){
 int s[2];assert(!socketpair(AF_UNIX,SOCK_STREAM,0,s));
 struct vmweave_ipc c=VMWEAVE_IPC_INIT;assert(!vmweave_ipc_create(&c));
 unsigned char h[64]={0},scratch[64];put(h,MAGIC,4);put(h+4,1,4);put(h+16,1,8);
 put(h+offset,value,width);assert(!io(s[0],h,64,1));shutdown(s[0],SHUT_WR);
 uint32_t api;const void *in;size_t n,cap;void *out;unsigned mode;
 assert(vmweave_ipc_receive(&c,s[1],scratch,sizeof(scratch),&api,&in,&n,&out,&cap,&mode)==-1);
 assert(!c.sequence);close(s[0]);close(s[1]);vmweave_ipc_close(&c);
}
static void bad_response(unsigned offset,uint64_t value,unsigned width){
 int s[2];assert(!socketpair(AF_UNIX,SOCK_STREAM,0,s));
 struct vmweave_ipc c=VMWEAVE_IPC_INIT;assert(!vmweave_ipc_create(&c));
 unsigned char h[64]={0};put(h,MAGIC,4);put(h+4,1,4);put(h+16,1,8);
 put(h+offset,value,width);assert(!io(s[1],h,64,1));shutdown(s[1],SHUT_WR);
 unsigned char out[16];memset(out,0xcc,sizeof(out));uint32_t t,d,r;size_t got=123;
 assert(vmweave_ipc_call(&c,s[0],0x1001,NULL,0,out,sizeof(out),&t,&d,&r,&got)==-1&&!got);
 for(unsigned i=0;i<sizeof(out);i++)assert(out[i]==0xcc);
 close(s[0]);close(s[1]);vmweave_ipc_close(&c);
}
int main(void){
 const unsigned offsets[]={0,4,8,12,16,24,32,40,44,48,52,56};
 for(unsigned i=0;i<sizeof(offsets)/sizeof(offsets[0]);i++){
  unsigned o=offsets[i];if(o!=12)bad_request(o,o==8?3:o==24||o==32?VMWEAVE_IPC_HALF+1:99,o==16||o==24||o==32||o==56?8:4);
  /* Transport/domain/result are payload fields; nonzero is a valid reply. */
  if(o!=40&&o!=44&&o!=48)bad_response(o,99,o==16||o==24||o==32||o==56?8:4);
 }
 bad_request(24,1,8); /* Inline body truncated at EOF. */
 int s[2];assert(!socketpair(AF_UNIX,SOCK_STREAM,0,s));
 struct vmweave_ipc c=VMWEAVE_IPC_INIT;assert(!vmweave_ipc_create(&c));assert(!vmweave_ipc_enable_events(&c));
 assert(!notify(c.request_event));assert(!await_event(c.request_event,s[0])); /* notify before wait */
 assert(!notify(c.request_event));assert(!notify(c.request_event));assert(await_event(c.request_event,s[0])==-1);
 pid_t child=fork();assert(child>=0);
 if(!child){usleep(20000);assert(!notify(c.request_event));_exit(0);}
 assert(!await_event(c.request_event,s[0]));int status;assert(waitpid(child,&status,0)==child&&WIFEXITED(status)&&!WEXITSTATUS(status));
 close(s[1]);assert(await_event(c.request_event,s[0])==-1);close(s[0]);
 assert(!socketpair(AF_UNIX,SOCK_STREAM,0,s));
 struct timespec a,b;clock_gettime(CLOCK_MONOTONIC,&a);
 assert(await_event(c.request_event,s[0])==-1); /* Production 20-second deadline. */
 clock_gettime(CLOCK_MONOTONIC,&b);assert(b.tv_sec-a.tv_sec>=19&&b.tv_sec-a.tv_sec<=23);
 close(s[0]);close(s[1]);vmweave_ipc_close(&c);
 int unsealed=memfd_create("unsealed-test",MFD_ALLOW_SEALING);assert(unsealed>=0);
 assert(!ftruncate(unsealed,VMWEAVE_IPC_ARENA_BYTES));assert(vmweave_ipc_map(&c,unsealed)==-1);close(unsealed);
 puts("PASS malformed request/reply, truncation, output canaries, event order/count/peer death/deadline, unsealed map");
}
