#define _GNU_SOURCE
#include "vmweave_session_ipc.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <unistd.h>
static void put(unsigned char *p,uint64_t v,unsigned n){for(unsigned i=0;i<n;i++)p[i]=(unsigned char)(v>>(8*i));}
int main(int argc,char **argv){
 int events=argc>1&&!strcmp(argv[1],"events"),fd[2];assert(!socketpair(AF_UNIX,SOCK_STREAM,0,fd));
 struct vmweave_ipc c=VMWEAVE_IPC_INIT;assert(!vmweave_ipc_create(&c));if(events)assert(!vmweave_ipc_enable_events(&c));
 size_t n=1024*1024;pid_t pid=fork();assert(pid>=0);
 if(!pid){
  close(fd[0]);assert(!vmweave_ipc_handshake(fd[1],1));unsigned char *scratch=malloc(VMWEAVE_IPC_HALF);assert(scratch);
  for(int step=0;step<2;step++){
   uint32_t api;const void *in;size_t bytes,cap;void *out;unsigned mode;
   assert(!vmweave_ipc_receive(&c,fd[1],scratch,VMWEAVE_IPC_HALF,&api,&in,&bytes,&out,&cap,&mode));assert(api==0x1012&&mode==(unsigned)step+1);
   if(!step){assert(bytes==48+n);for(size_t i=0;i<n;i++)assert(((unsigned char*)in)[48+i]==0x5a);}
   else memset(out,0xa5,n);
   assert(!vmweave_ipc_reply(&c,fd[1],mode,0,1,0,out,step?n:0));
  }
  free(scratch);vmweave_ipc_close(&c);close(fd[1]);_exit(0);
 }
 close(fd[1]);assert(!vmweave_ipc_handshake(fd[0],0));unsigned char *in=calloc(1,n+48),*out=malloc(n);assert(in&&out);
 put(in,1,4);put(in+40,n,8);memset(in+48,0x5a,n);uint32_t t,d,e;size_t got;
 assert(!vmweave_ipc_call(&c,fd[0],0x1012,in,48+n,out,n,&t,&d,&e,&got)&&!t&&!e&&!got);
 put(in,2,4);assert(!vmweave_ipc_call(&c,fd[0],0x1012,in,48,out,n,&t,&d,&e,&got)&&got==n);
 for(size_t i=0;i<n;i++)assert(out[i]==0xa5);
 int status;assert(waitpid(pid,&status,0)==pid&&WIFEXITED(status)&&WEXITSTATUS(status)==0);
 close(fd[0]);vmweave_ipc_close(&c);assert(c.fd==-1&&c.request_event==-1&&c.response_event==-1);free(in);free(out);
 puts("PASS host arena/socket protocol and optional event notifications");
}
