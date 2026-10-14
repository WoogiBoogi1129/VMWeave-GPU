#define _GNU_SOURCE
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>
#include <pthread.h>
#include "flyt_sessions.h"
#define MAGIC 0x32574d56u
static int fd=-1,failed;static pid_t owner;static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
static int io(void *p,size_t n,int write){while(n){ssize_t k=write?send(fd,p,n,MSG_NOSIGNAL):recv(fd,p,n,0);if(k<0&&errno==EINTR)continue;if(k<=0)return -1;p=(char*)p+k;n-=k;}return 0;}
int flyt_broker_exchange(uint32_t api,const void *in,size_t n,void *out,size_t cap,size_t *got){
 if(owner&&owner!=getpid())return 999;
 if(n>FLYT_SESSION_MAX_BYTES||cap>FLYT_SESSION_MAX_BYTES)return 1;
 pthread_mutex_lock(&lock);int result=999;*got=0;if(failed)goto done;
 if(fd<0){
  const char *path=getenv("FLYT_BROKER_SOCKET");struct sockaddr_un addr={.sun_family=AF_UNIX};
  if(!path||strlen(path)>=sizeof(addr.sun_path))goto bad;strcpy(addr.sun_path,path);
  fd=socket(AF_UNIX,SOCK_STREAM|SOCK_CLOEXEC,0);if(fd<0)goto bad;owner=getpid();
  struct timeval t={.tv_sec=30};setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&t,sizeof(t));setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&t,sizeof(t));
  if(connect(fd,(struct sockaddr*)&addr,sizeof(addr)))goto bad;
 }
 struct {uint32_t magic,api;uint64_t bytes,capacity;} q={MAGIC,api,n,cap};
 struct {uint32_t magic,result;uint64_t bytes;} r;
 if(io(&q,sizeof(q),1)||io((void*)in,n,1)||io(&r,sizeof(r),0)||r.magic!=MAGIC||r.bytes>cap||io(out,r.bytes,0))goto bad;
 *got=r.bytes;result=r.result;goto done;
 bad:failed=1;if(fd>=0){close(fd);fd=-1;}
 done:pthread_mutex_unlock(&lock);return result;
}
void flyt_broker_close(void){
 if(owner!=getpid()||fd<0)return;size_t got;flyt_broker_exchange(2,NULL,0,NULL,0,&got);close(fd);fd=-1;failed=1;
}
