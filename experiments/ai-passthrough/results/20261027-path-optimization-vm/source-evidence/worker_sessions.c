#define _GNU_SOURCE
#include "vmweave_wire.h"
#include "vmweave_async.h"
#include "vmweave_compat.h"
#include "vmweave_torch.h"
#include "vmweave_sessions.h"
#include "vmweave_perf.h"
#include "vmweave_session_ipc.h"
#include <fcntl.h>
#include <sys/time.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <sys/prctl.h>
#include <poll.h>
#include <signal.h>
#include <errno.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

struct message { uint32_t api, transport, domain, result; uint64_t bytes; };
static volatile sig_atomic_t stopped;
static void stop(int sig){(void)sig;stopped=1;}
static int transfer(int fd,void *buf,size_t n,int writing){
 char *p=buf;while(n){ssize_t r=writing?send(fd,p,n,MSG_NOSIGNAL):recv(fd,p,n,0);if(r<0&&errno==EINTR&&!stopped)continue;if(r<=0)return -1;p+=r;n-=r;}return 0;
}
/* This executable instance owns one CUDA context lifetime. No parent CUDA calls. */
static struct vmweave_ipc parent_ipc=VMWEAVE_IPC_INIT;
static int ipc_enabled,event_enabled;
static int execute_session(int fd,int arena_fd,int request_event,int response_event){
 struct vmweave_ipc child_ipc=VMWEAVE_IPC_INIT;int arena=arena_fd>=0;
 child_ipc.request_event=request_event;child_ipc.response_event=response_event;
 struct timeval timeout={.tv_sec=20};
 if(setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout))||setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout)))return 1;
 if(arena&&(vmweave_ipc_map(&child_ipc,arena_fd)||vmweave_ipc_handshake(fd,1)))return 1;
 struct vmweave_cuda_runtime *runtime=NULL;struct vmweave_cuda_session session={0};uint32_t error=0;
 if(vmweave_cuda_runtime_open(&runtime,&error)||vmweave_cuda_exec_create(vmweave_cuda_runtime_backend(),runtime,&session.exec))return 1;
 unsigned char *in=malloc(VMWEAVE_SESSION_MAX_BYTES),*out=malloc(VMWEAVE_SESSION_MAX_BYTES);if(!in||!out)return 1;
 struct message m;
 while(1){
  if(vmweave_async_reap())break;
  struct pollfd pending[2]={{.fd=arena?vmweave_ipc_request_wait_fd(&child_ipc,fd):fd,.events=POLLIN},{.fd=fd,.events=0}};
  int ready=poll(pending,2,10);
  if(ready>0&&!(pending[0].revents&POLLIN))break;
  if(ready==0)continue;if(ready<0)break;
  const void *input=in;void *output=out;size_t bytes=0,capacity=VMWEAVE_SESSION_MAX_BYTES;uint32_t api=0;unsigned mode=0;
  if(arena){
   if(vmweave_ipc_receive(&child_ipc,fd,in,VMWEAVE_SESSION_MAX_BYTES,&api,&input,&bytes,&output,&capacity,&mode))break;
  }else{
   if(transfer(fd,&m,sizeof(m),0)||m.bytes>VMWEAVE_SESSION_MAX_BYTES||transfer(fd,in,m.bytes,0))break;
   api=m.api;bytes=m.bytes;
  }
  struct vmweave_shm_request q={.api_id=api,.payload_schema=1,.input=input,.input_bytes=bytes};
  struct vmweave_shm_response r={.output=output,.output_capacity=capacity};int rc=0;
  if(vmweave_cuda_exec_check(session.exec)!=VMWEAVE_SHM_OK)break;
  if(q.api_id>=0x3000)rc=vmweave_compat_dispatch(&session,&q,&r);
  else if(q.api_id>=0x2100&&q.api_id!=VMWEAVE_STREAM_PRIORITY_CREATE)rc=vmweave_torch_dispatch(&session,&q,&r);
  else if(q.api_id>=0x2000)rc=vmweave_async_dispatch(&session,&q,&r);
  else rc=vmweave_cuda_dispatch(&session,&q,&r);
  if(rc||r.output_bytes>capacity)break;
  m=(struct message){.transport=r.transport_status,.domain=r.result_domain,.result=r.api_result,.bytes=r.output_bytes};
  if(arena){if(vmweave_ipc_reply(&child_ipc,fd,mode,r.transport_status,r.result_domain,r.api_result,output,r.output_bytes))break;}
  else if(transfer(fd,&m,sizeof(m),1)||transfer(fd,out,m.bytes,1))break;
 }
 /* Exit releases CUDA, libraries and outstanding asynchronous work together. */
 if(arena)vmweave_ipc_close(&child_ipc);free(in);free(out);return 0;
}
static int retire(pid_t *pid,int *fd){
 if(*fd>=0){close(*fd);*fd=-1;}
 if(*pid>0){kill(*pid,SIGKILL);pid_t n;do{n=waitpid(*pid,NULL,0);}while(n<0&&errno==EINTR);if(n!=*pid)return -1;*pid=0;}vmweave_ipc_close(&parent_ipc);return 0;
}
static int spawn(pid_t *pid,int *fd){
 int fds[2];if(socketpair(AF_UNIX,SOCK_STREAM,0,fds))return -1;
 if(ipc_enabled&&(vmweave_ipc_create(&parent_ipc)||(event_enabled&&vmweave_ipc_enable_events(&parent_ipc)))){close(fds[0]);close(fds[1]);vmweave_ipc_close(&parent_ipc);return -1;}
 *pid=fork();if(*pid<0){close(fds[0]);close(fds[1]);vmweave_ipc_close(&parent_ipc);return -1;}
 if(!*pid){
  close(fds[0]);prctl(PR_SET_PDEATHSIG,SIGKILL);if(getppid()==1)_exit(1);
  char number[24];snprintf(number,sizeof(number),"%d",fds[1]);
  for(int i=3;i<1024;i++)if(i!=fds[1]&&i!=parent_ipc.fd&&i!=parent_ipc.request_event&&i!=parent_ipc.response_event)close(i);
  if(ipc_enabled){
   char descriptor[24];snprintf(descriptor,sizeof(descriptor),"%d",parent_ipc.fd);
   if(fcntl(parent_ipc.fd,F_SETFD,0))_exit(1);
   if(event_enabled){
    char request[24],response[24];snprintf(request,sizeof(request),"%d",parent_ipc.request_event);snprintf(response,sizeof(response),"%d",parent_ipc.response_event);
    if(fcntl(parent_ipc.request_event,F_SETFD,0)||fcntl(parent_ipc.response_event,F_SETFD,0))_exit(1);
    execl("/proc/self/exe","vmweave-shm-session-worker","--session-events",number,descriptor,request,response,NULL);_exit(1);
   }
   execl("/proc/self/exe","vmweave-shm-session-worker","--session-arena",number,descriptor,NULL);_exit(1);
  }
  execl("/proc/self/exe","vmweave-shm-session-worker","--session",number,NULL);_exit(1);
 }
 close(fds[1]);*fd=fds[0];struct timeval timeout={.tv_sec=20};
 if(setsockopt(*fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout))||setsockopt(*fd,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout))||
    (ipc_enabled&&vmweave_ipc_handshake(*fd,0))){retire(pid,fd);return -1;}return 0;
}
int main(int argc,char **argv){
 if(argc==3&&!strcmp(argv[1],"--session"))return execute_session(atoi(argv[2]),-1,-1,-1);
 if(argc==4&&!strcmp(argv[1],"--session-arena"))return execute_session(atoi(argv[2]),atoi(argv[3]),-1,-1);
 if(argc==6&&!strcmp(argv[1],"--session-events"))return execute_session(atoi(argv[2]),atoi(argv[3]),atoi(argv[4]),atoi(argv[5]));
 const char *ipc_env=getenv("VMWEAVE_SESSION_ARENA");ipc_enabled=ipc_env&&!strcmp(ipc_env,"1");
 const char *event_env=getenv("VMWEAVE_SESSION_EVENTFD");event_enabled=event_env&&!strcmp(event_env,"1");
 if(event_enabled&&!ipc_enabled)return 2;
 if(argc!=3)return 2;char *end;unsigned long slot=strtoul(argv[2],&end,10);if(*end||slot>=32)return 2;
 struct vmweave_shm_layout l;struct vmweave_mapping m={0};struct vmweave_shm_channel *c=NULL;
 char path[512],marker[128],guest[128];snprintf(path,sizeof(path),"%s/layout.bin",argv[1]);
 if(vmweave_layout_read(path,&l))return 3;snprintf(path,sizeof(path),"%s/channel",argv[1]);
 if(vmweave_map_file(path,&l,&m)||vmweave_shm_open(m.address,m.bytes,&l,slot,VMWEAVE_SHM_WORKER,30000,&c))return 3;
 signal(SIGTERM,stop);signal(SIGINT,stop);
 snprintf(marker,sizeof(marker),"/tmp/vmweave-slot-%lu-mapped",slot);FILE *f=fopen(marker,"wx");if(!f)return 4;fclose(f);
 snprintf(guest,sizeof(guest),"/tmp/vmweave-slot-%lu-guest",slot);
 size_t capacity=vmweave_shm_response_capacity(c);unsigned char *output=malloc(capacity);if(!output)return 4;
 const char *reuse_env=getenv("VMWEAVE_WORKER_REUSE");
 int reuse=reuse_env&&!strcmp(reuse_env,"1");
 unsigned char *scratch=reuse?malloc(VMWEAVE_SHM_MAX_MESSAGE_BYTES):NULL;if(reuse&&!scratch)return 4;
 pid_t pid=0;int fd=-1,hello=0;unsigned char epoch[16]={0};int active=0;struct vmweave_wait idle={0};
 while(!stopped){
  struct vmweave_shm_request q={0};int rc=reuse?vmweave_shm_worker_take_into(c,&q,scratch,VMWEAVE_SHM_MAX_MESSAGE_BYTES):vmweave_shm_worker_take(c,&q);
  if(rc==VMWEAVE_SHM_AGAIN){if(vmweave_wait_pause(&idle))break;continue;}if(rc)break;memset(&idle,0,sizeof(idle));
  struct vmweave_shm_response r={.output=output,.output_capacity=capacity,.result_domain=VMWEAVE_RESULT_LIBRARY};
  if(q.payload_schema!=1){r.api_result=999;}
  else if(q.api_id==VMWEAVE_HELLO&&!hello&&!q.input_bytes){hello=1;}
  else if(!hello){r.api_result=999;}
  else if(q.api_id==VMWEAVE_HEARTBEAT&&!q.input_bytes){}
  else if(q.api_id==VMWEAVE_GOODBYE&&!q.input_bytes){retire(&pid,&fd);active=0;stopped=1;}
  else if(q.api_id==VMWEAVE_SESSION_OPEN&&q.input_bytes==16&&!active){
   if(!memcmp(q.input,(unsigned char[16]){0},16)||spawn(&pid,&fd))r.api_result=999;
   else{memcpy(epoch,q.input,16);active=1;}
  }else if(q.api_id==VMWEAVE_SESSION_CLOSE&&q.input_bytes==16&&active&&!memcmp(epoch,q.input,16)){
   if(retire(&pid,&fd)){r.api_result=999;stopped=1;}active=0;memset(epoch,0,16);
  }else if(q.api_id==VMWEAVE_SESSION_STATUS&&active&&q.input_bytes==16&&!memcmp(epoch,q.input,16)){
   /* A dead child closes its socket even when no CUDA requests are pending.
    * Do not reap here: CLOSE remains responsible for retiring this epoch. */
   struct pollfd health={.fd=fd,.events=POLLIN};
   int ready=fd>=0?poll(&health,1,0):-1;
   if(ready<0||(ready>0&&(health.revents&(POLLHUP|POLLERR|POLLNVAL|POLLIN)))||capacity<16)r.api_result=999;
   else{memcpy(output,epoch,16);r.output_bytes=16;}
  }else if(q.api_id==VMWEAVE_SESSION_CALL&&active&&q.input_bytes>=VMWEAVE_SESSION_ENVELOPE&&q.input_bytes-VMWEAVE_SESSION_ENVELOPE<=VMWEAVE_SESSION_MAX_BYTES&&!memcmp(q.input,epoch,16)&&!vmweave_get((const unsigned char*)q.input+20,4)){
   uint32_t api=vmweave_get((const unsigned char*)q.input+16,4);
   struct message msg={.api=api,.bytes=q.input_bytes-VMWEAVE_SESSION_ENVELOPE};struct pollfd pollfd={.fd=fd,.events=POLLIN};
   if(ipc_enabled){
    size_t produced=0;
    if(api<0x1000||fd<0||vmweave_ipc_call(&parent_ipc,fd,api,(char*)q.input+VMWEAVE_SESSION_ENVELOPE,msg.bytes,output,capacity,
       &r.transport_status,&r.result_domain,&r.api_result,&produced)){
     retire(&pid,&fd);r.api_result=999;r.output_bytes=0;
    }else r.output_bytes=produced;
   }else if(api<0x1000||fd<0||transfer(fd,&msg,sizeof(msg),1)||transfer(fd,(char*)q.input+VMWEAVE_SESSION_ENVELOPE,msg.bytes,1)||poll(&pollfd,1,20000)<=0||transfer(fd,&msg,sizeof(msg),0)||msg.bytes>capacity||transfer(fd,output,msg.bytes,0)){
    retire(&pid,&fd);r.api_result=999;
   }else{r.transport_status=msg.transport;r.result_domain=msg.domain;r.api_result=msg.result;r.output_bytes=msg.bytes;}
  }else r.api_result=999;
  rc=vmweave_shm_worker_respond(c,&r);if(reuse)vmweave_shm_request_clear_borrowed(&q);else vmweave_shm_request_release(&q);if(rc)break;
  if(hello){f=fopen(guest,"a");if(f)fclose(f);}
 }
 retire(&pid,&fd);unlink(marker);unlink(guest);free(scratch);free(output);vmweave_shm_close(c);vmweave_unmap(&m);return 0;
}
