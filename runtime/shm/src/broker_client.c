#define _GNU_SOURCE
#include "vmweave_env.h"
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>
#include <pthread.h>
#include <stdatomic.h>
#include <poll.h>
#include <time.h>
#include "vmweave_sessions.h"
#define MAGIC 0x32574d56u
#define GET_DEVICE 0x1002u
#define SET_DEVICE 0x1003u
#define PRIMARY_STATE 0x2107u
/* Lease is a maximum local reuse window, not an instantaneous remote check.
 * An expired lease requires a synchronous STATUS, even if broker is stalled. */
#define LEASE_NS 50000000ull
static int fd=-1,failed,negotiated,cache_enabled;
static _Atomic pid_t owner;
static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
static unsigned char epoch[16],device[4],primary[8];
static int have_device,have_primary;
static uint64_t lease,device_hits,primary_hits,wire_calls,health_checks,invalidations;
static uint64_t now(void){struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return 0;return (uint64_t)t.tv_sec*1000000000ull+t.tv_nsec;}
static void invalidate(void){have_device=have_primary=0;++invalidations;}
static void fail(void){invalidate();failed=1;cache_enabled=0;if(fd>=0){close(fd);fd=-1;}}
static int io(void *p,size_t n,int writing){
 while(n){ssize_t k=writing?send(fd,p,n,MSG_NOSIGNAL):recv(fd,p,n,0);
  if(k<0&&errno==EINTR)continue;if(k<=0)return -1;p=(char*)p+k;n-=k;
 }return 0;
}
/* Caller holds lock. No cache logic here, including for health controls. */
static int request(uint32_t api,const void *in,size_t n,void *out,size_t cap,size_t *got){
 struct {uint32_t magic,api;uint64_t bytes,capacity;} q={MAGIC,api,n,cap};
 struct {uint32_t magic,result;uint64_t bytes;} r;
 *got=0;++wire_calls;
 if(io(&q,sizeof(q),1)||io((void*)in,n,1)||io(&r,sizeof(r),0)||r.magic!=MAGIC||r.bytes>cap||io(out,r.bytes,0)){
  fail();return 999;
 }
 *got=r.bytes;return r.result;
}
static int connected(void){
 const char *path=vmweave_getenv("VMWEAVE_BROKER_SOCKET");struct sockaddr_un addr={.sun_family=AF_UNIX};
 if(!path||strlen(path)>=sizeof(addr.sun_path))return -1;strcpy(addr.sun_path,path);
 fd=socket(AF_UNIX,SOCK_STREAM|SOCK_CLOEXEC,0);if(fd<0)return -1;
 struct timeval t={.tv_sec=30};
 if(setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&t,sizeof(t))||setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&t,sizeof(t)))return -1;
 return connect(fd,(struct sockaddr*)&addr,sizeof(addr));
}
static void negotiate(void){
 negotiated=1;const char *enabled=vmweave_getenv("VMWEAVE_STATE_CACHE");
 if(!enabled||strcmp(enabled,"1"))return;
 unsigned char reply[24];size_t got;uint64_t start=now();
 int rc=request(VMWEAVE_BROKER_CACHE_OPEN,NULL,0,reply,sizeof(reply),&got);
 if(rc||got!=24)return; /* Legacy peer: no cache. Transport failure remains sticky. */
 uint32_t version,flags;memcpy(&version,reply,4);memcpy(&flags,reply+4,4);
 if(got!=24||version!=VMWEAVE_BROKER_CACHE_VERSION||flags!=1||!memcmp(reply+8,(unsigned char[16]){0},16))return;
 memcpy(epoch,reply+8,16);cache_enabled=1;lease=start+LEASE_NS;
}
static int healthy(void){
 struct pollfd p={.fd=fd,.events=POLLIN};int ready;
 do{ready=poll(&p,1,0);}while(ready<0&&errno==EINTR);
 /* Nothing should be readable between synchronous requests. EOF and stray
  * replies both fence this session instead of returning a cached success. */
 if(ready<0||(ready>0&&p.revents)){fail();return 0;}
 uint64_t start=now();
 if(!start||start>=lease){
  unsigned char reply[16];size_t got;++health_checks;
  if(request(VMWEAVE_BROKER_CACHE_STATUS,NULL,0,reply,16,&got)||got!=16||memcmp(reply,epoch,16)){
   fail();return 0;
  }
  lease=start+LEASE_NS;
 }
 return 1;
}
int vmweave_broker_exchange(uint32_t api,const void *in,size_t n,void *out,size_t cap,size_t *got){
 if(got)*got=0;
 /* This precedes the inherited mutex, including when another thread forked. */
 if(owner&&owner!=getpid())return 999;
 if(!got||(n&&!in)||(cap&&!out)||n>VMWEAVE_SESSION_MAX_BYTES||cap>VMWEAVE_SESSION_MAX_BYTES)return 1;
 pid_t unset=0;atomic_compare_exchange_strong(&owner,&unset,getpid());
 if(owner!=getpid())return 999;
 pthread_mutex_lock(&lock);int result=999;
 if(failed)goto done;
 if(fd<0&&connected()){fail();goto done;}
 if(!negotiated)negotiate();
 if(failed)goto done;
 if(cache_enabled&&!healthy())goto done;
 if(cache_enabled&&!n){
  if(api==GET_DEVICE&&have_device&&cap>=4){memcpy(out,device,4);*got=4;++device_hits;result=0;goto done;}
  if(api==PRIMARY_STATE&&have_primary&&cap>=8){memcpy(out,primary,8);*got=8;++primary_hits;result=0;goto done;}
 }
 if(api==SET_DEVICE||api==2)invalidate();
 result=request(api,in,n,out,cap,got);
 if(result){invalidate();if(result==999&&cache_enabled)fail();goto done;}
 if(cache_enabled&&!n){
  if(api==GET_DEVICE&&*got==4&&!memcmp(out,(unsigned char[4]){0},4)){memcpy(device,out,4);have_device=1;}
  if(api==PRIMARY_STATE&&*got==8){int active;memcpy(&active,(char*)out+4,4);
   if(active==1){memcpy(primary,out,8);have_primary=1;}
  }
 }
 if(api==2)fail();
 done:pthread_mutex_unlock(&lock);return result;
}
void vmweave_broker_close(void){
 if(owner!=getpid())return;
 pthread_mutex_lock(&lock);
 if(fd>=0&&!failed){size_t got;request(2,NULL,0,NULL,0,&got);}
 fail();pthread_mutex_unlock(&lock);
}
/* Diagnostic counters, cumulative for this process; no reset races. */
void vmweave_broker_cache_stats(uint64_t out[6]){
 if(!out)return;
 pid_t unset=0;atomic_compare_exchange_strong(&owner,&unset,getpid());
 if(owner!=getpid()){memset(out,0,6*sizeof(*out));return;}
 pthread_mutex_lock(&lock);
 out[0]=cache_enabled;out[1]=device_hits;out[2]=primary_hits;
 out[3]=wire_calls;out[4]=health_checks;out[5]=invalidations;
 pthread_mutex_unlock(&lock);
}

/* Legacy binary ABI: same implementation and address, no second state. */
extern __typeof__(vmweave_broker_cache_stats) flyt_broker_cache_stats __attribute__((alias("vmweave_broker_cache_stats")));
extern __typeof__(vmweave_broker_close) flyt_broker_close __attribute__((alias("vmweave_broker_close")));
extern __typeof__(vmweave_broker_exchange) flyt_broker_exchange __attribute__((alias("vmweave_broker_exchange")));
