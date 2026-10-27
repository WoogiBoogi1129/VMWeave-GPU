#define _GNU_SOURCE
#include "vmweave_session_ipc.h"
#include <sys/mman.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/eventfd.h>
#include <poll.h>
#include <time.h>
#include <stdatomic.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#define MAGIC 0x31505756u
#define SEALS (F_SEAL_GROW|F_SEAL_SHRINK|F_SEAL_SEAL)
static uint64_t get(const unsigned char *p,unsigned n){uint64_t v=0;for(unsigned i=0;i<n;i++)v|=(uint64_t)p[i]<<(8*i);return v;}
static void put(unsigned char *p,uint64_t v,unsigned n){for(unsigned i=0;i<n;i++)p[i]=(unsigned char)(v>>(8*i));}
static int io(int fd,void *p,size_t n,int write){
 while(n){ssize_t k=write?send(fd,p,n,MSG_NOSIGNAL):recv(fd,p,n,0);
  if(k<0&&errno==EINTR)continue;if(k<=0)return -1;p=(char*)p+k;n-=(size_t)k;}return 0;
}
int vmweave_ipc_map(struct vmweave_ipc *c,int fd){
 struct stat st;int seals=fcntl(fd,F_GET_SEALS);
 if(fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_size!=VMWEAVE_IPC_ARENA_BYTES||seals<0||(seals&SEALS)!=SEALS)return -1;
 void *p=mmap(NULL,VMWEAVE_IPC_ARENA_BYTES,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
 if(p==MAP_FAILED)return -1;c->arena=p;c->fd=fd;c->sequence=0;return 0;
}
int vmweave_ipc_create(struct vmweave_ipc *c){
 int fd=memfd_create("vmweave-host-session",MFD_ALLOW_SEALING|MFD_CLOEXEC);if(fd<0)return -1;
 if(ftruncate(fd,VMWEAVE_IPC_ARENA_BYTES)||fcntl(fd,F_ADD_SEALS,SEALS)||vmweave_ipc_map(c,fd)){close(fd);return -1;}return 0;
}
int vmweave_ipc_enable_events(struct vmweave_ipc *c){
 c->request_event=eventfd(0,EFD_CLOEXEC|EFD_NONBLOCK);if(c->request_event<0)return -1;
 c->response_event=eventfd(0,EFD_CLOEXEC|EFD_NONBLOCK);
 if(c->response_event<0){close(c->request_event);c->request_event=-1;return -1;}return 0;
}
int vmweave_ipc_request_wait_fd(const struct vmweave_ipc *c,int socket){return c->request_event>=0?c->request_event:socket;}
static int notify(int fd){
 if(fd<0)return 0;uint64_t one=1;ssize_t n;do{n=write(fd,&one,sizeof(one));}while(n<0&&errno==EINTR);
 return n==sizeof(one)?0:-1;
}
static int await_event(int event,int socket){
 if(event<0)return 0;
 struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return -1;
 int64_t deadline=(int64_t)t.tv_sec*1000+t.tv_nsec/1000000+20000;
 for(;;){
  if(clock_gettime(CLOCK_MONOTONIC,&t))return -1;
  int64_t remaining=deadline-((int64_t)t.tv_sec*1000+t.tv_nsec/1000000);if(remaining<=0)return -1;
  struct pollfd fds[2]={{.fd=event,.events=POLLIN},{.fd=socket,.events=0}};
  int rc=poll(fds,2,(int)remaining);if(rc<0&&errno==EINTR)continue;if(rc<=0)return -1;
  if(fds[0].revents&POLLIN){uint64_t count;ssize_t n=read(event,&count,sizeof(count));
   if(n==sizeof(count)&&count==1)return 0;return -1;}
  if(fds[1].revents&(POLLHUP|POLLERR|POLLNVAL))return -1;
  return -1;
 }
}
void vmweave_ipc_close(struct vmweave_ipc *c){if(c->arena)munmap(c->arena,VMWEAVE_IPC_ARENA_BYTES);if(c->fd>=0)close(c->fd);if(c->request_event>=0)close(c->request_event);if(c->response_event>=0)close(c->response_event);*c=(struct vmweave_ipc)VMWEAVE_IPC_INIT;}
int vmweave_ipc_handshake(int fd,int child){
 unsigned char hello[8]={0},other[8];put(hello,MAGIC,4);put(hello+4,1,4);
 if(child){if(io(fd,hello,8,1)||io(fd,other,8,0))return -1;}
 else if(io(fd,other,8,0)||memcmp(hello,other,8)||io(fd,hello,8,1))return -1;
 return memcmp(hello,other,8)?-1:0;
}
/* 64-byte private socket descriptor: magic/version/mode/api/sequence/input bytes/
 * output capacity/transport/domain/result/reserved/produced bytes. */
static int header(const unsigned char *h){return get(h,4)==MAGIC&&get(h+4,4)==1&&!get(h+52,4);}
int vmweave_ipc_call(struct vmweave_ipc *c,int fd,uint32_t api,const void *input,size_t n,void *out,size_t cap,
 uint32_t *transport,uint32_t *domain,uint32_t *result,size_t *got){
 unsigned char h[64]={0},r[64];unsigned mode=0;size_t wire=n;*got=0;if(cap>VMWEAVE_IPC_HALF)cap=VMWEAVE_IPC_HALF;
 if(!c->arena||c->sequence==UINT64_MAX||n>VMWEAVE_IPC_HALF||cap>VMWEAVE_IPC_HALF||(n&&!input)||(cap&&!out))return -1;
 const unsigned char *p=input;
 if(api==0x1012u&&n>=48&&!get(p+4,4)){
  uint64_t bytes=get(p+40,8),kind=get(p,4);
  if(bytes>=1024u*1024u&&bytes<=16u*1024u*1024u){
   if(kind==1&&n==48+bytes){mode=1;memcpy(c->arena+48,p+48,(size_t)bytes);wire=48;}
   else if(kind==2&&n==48&&cap>=bytes)mode=2;
  }
 }
 put(h,MAGIC,4);put(h+4,1,4);put(h+8,mode,4);put(h+12,api,4);put(h+16,++c->sequence,8);put(h+24,n,8);put(h+32,cap,8);
 atomic_thread_fence(memory_order_release);
 if(io(fd,h,64,1)||notify(c->request_event)||io(fd,(void*)input,wire,1)||await_event(c->response_event,fd)||io(fd,r,64,0)||!header(r)||
    get(r+8,4)!=mode||get(r+12,4)||get(r+16,8)!=c->sequence||get(r+24,8)||get(r+32,8))return -1;
 atomic_thread_fence(memory_order_acquire);
 uint64_t produced=get(r+56,8);if(produced>cap||produced>VMWEAVE_IPC_HALF)return -1;
 *transport=(uint32_t)get(r+40,4);*domain=(uint32_t)get(r+44,4);*result=(uint32_t)get(r+48,4);
 if((*transport||*result)&&produced)return -1;
 if(mode==2){
  if(!*transport&&!*result&&produced!=get(p+40,8))return -1;
  if(produced)memcpy(out,c->arena+VMWEAVE_IPC_HALF,(size_t)produced);
 }else if(io(fd,out,(size_t)produced,0))return -1;
 *got=(size_t)produced;return 0;
}
int vmweave_ipc_receive(struct vmweave_ipc *c,int fd,void *scratch,size_t scratch_cap,uint32_t *api,
 const void **input,size_t *bytes,void **output,size_t *capacity,unsigned *mode){
 unsigned char h[64];if(await_event(c->request_event,fd)||io(fd,h,64,0)||!header(h)||c->sequence==UINT64_MAX||get(h+16,8)!=c->sequence+1||
 get(h+40,4)||get(h+44,4)||get(h+48,4)||get(h+56,8))return -1;
 atomic_thread_fence(memory_order_acquire);
 uint64_t n=get(h+24,8),cap=get(h+32,8),m=get(h+8,4);
 if(n>scratch_cap||n>VMWEAVE_IPC_HALF||cap>VMWEAVE_IPC_HALF||m>2)return -1;
 *api=(uint32_t)get(h+12,4);*bytes=(size_t)n;*capacity=(size_t)cap;*mode=(unsigned)m;
 if(m){
  unsigned char descriptor[48];if(*api!=0x1012u||n<48||io(fd,descriptor,48,0)||get(descriptor+4,4))return -1;
  uint64_t size=get(descriptor+40,8);
  if(size<1024u*1024u||size>16u*1024u*1024u||get(descriptor,4)!=m)return -1;
  if(m==1){if(n!=48+size)return -1;memcpy(c->arena,descriptor,48);*input=c->arena;}
  else{if(n!=48||cap<size)return -1;memcpy(scratch,descriptor,48);*input=scratch;}
 }else{if(io(fd,scratch,(size_t)n,0))return -1;*input=scratch;}
 *output=c->arena+VMWEAVE_IPC_HALF;++c->sequence;return 0;
}
int vmweave_ipc_reply(struct vmweave_ipc *c,int fd,unsigned mode,uint32_t transport,uint32_t domain,uint32_t result,const void *out,size_t n){
 if(n>VMWEAVE_IPC_HALF||(n&&!out)||mode>2)return -1;
 if(transport||result)n=0;
 unsigned char h[64]={0};put(h,MAGIC,4);put(h+4,1,4);put(h+8,mode,4);put(h+16,c->sequence,8);
 put(h+40,transport,4);put(h+44,domain,4);put(h+48,result,4);put(h+56,n,8);
 if(mode==2&&n&&out!=c->arena+VMWEAVE_IPC_HALF)return -1;
 atomic_thread_fence(memory_order_release);
 if(io(fd,h,64,1)||notify(c->response_event))return -1;return mode==2?0:io(fd,(void*)out,n,1);
}
