#define _GNU_SOURCE
#include "vmweave_env.h"
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
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
#define BLAS_CREATE 0x3101u
#define BLAS_DESTROY 0x3102u
#define BLAS_MATH_SET 0x3105u
#define MATH_CACHE_CAPACITY 64
/* Lease is a maximum local reuse window, not an instantaneous remote check.
 * An expired lease requires a synchronous STATUS, even if broker is stalled. */
#define LEASE_NS 50000000ull
#define BULK_OPEN 0x7ff2u
#define BULK_COPY 0x7ff3u
#define BULK_BYTES (16u*1024u*1024u)
#define BULK_THRESHOLD (1024u*1024u)
static unsigned char *bulk;
static int bulk_probed;
static int fd=-1,failed,negotiated,cache_enabled;
static _Atomic pid_t owner;
static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
static unsigned char epoch[16],device[4],primary[8];
static int have_device,have_primary;
/* Serialized with the exchange itself: a hit cannot race a setting mutation.
 * Keys use wire bytes to avoid alignment and host endianness assumptions. */
static struct { unsigned char key[12]; int valid; } math_cache[MATH_CACHE_CAPACITY];
static int math_cache_enabled;
static uint64_t math_hits,math_misses,math_invalidations,math_full;
static void invalidate_math(void){
 memset(math_cache,0,sizeof(math_cache));++math_invalidations;
}
static int math_match(const void *key){
 for(int i=0;i<MATH_CACHE_CAPACITY;i++)
  if(math_cache[i].valid&&!memcmp(math_cache[i].key,key,12))return 1;
 return 0;
}
static void remember_math(const void *key){
 int slot=-1;
 for(int i=0;i<MATH_CACHE_CAPACITY;i++)
  if(math_cache[i].valid&&!memcmp(math_cache[i].key,key,8)){slot=i;break;}
 if(slot<0)for(int i=0;i<MATH_CACHE_CAPACITY;i++)
  if(!math_cache[i].valid){slot=i;break;}
 if(slot<0){++math_full;return;}
 memcpy(math_cache[slot].key,key,12);math_cache[slot].valid=1;
}
static uint64_t lease,device_hits,primary_hits,wire_calls,health_checks,invalidations;
static uint64_t now(void){struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return 0;return (uint64_t)t.tv_sec*1000000000ull+t.tv_nsec;}
static void invalidate(void){have_device=have_primary=0;invalidate_math();++invalidations;}
static void fail(void){if(bulk){munmap(bulk,2*BULK_BYTES);bulk=NULL;}invalidate();failed=1;cache_enabled=0;if(fd>=0){close(fd);fd=-1;}}
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
/* Capability negotiation has no CUDA side effects; only an explicit unsupported
 * result permits fallback. Ambiguous transport failures fence the session. */
static void bulk_negotiate(void){
 bulk_probed=1;
 const char *enable=getenv("VMWEAVE_BULK_COPY");if(!enable||strcmp(enable,"1"))return;
 struct {uint32_t magic,api;uint64_t bytes,capacity;} q={MAGIC,BULK_OPEN,0,0};
 struct {uint32_t magic,result;uint64_t bytes;} r;
 if(io(&q,sizeof(q),1)){fail();return;}
 union {struct cmsghdr align;char bytes[CMSG_SPACE(sizeof(int)*4)];} control;
 struct iovec iov={&r,sizeof(r)};
 struct msghdr msg={0};msg.msg_iov=&iov;msg.msg_iovlen=1;msg.msg_control=control.bytes;msg.msg_controllen=sizeof(control);
 ssize_t n;do{n=recvmsg(fd,&msg,MSG_WAITALL|MSG_CMSG_CLOEXEC);}while(n<0&&errno==EINTR);
 int received=-1,count=0;
 for(struct cmsghdr *c=CMSG_FIRSTHDR(&msg);n>0&&c;c=CMSG_NXTHDR(&msg,c)){
  if(c->cmsg_level==SOL_SOCKET&&c->cmsg_type==SCM_RIGHTS){
   size_t k=(c->cmsg_len-CMSG_LEN(0))/sizeof(int);int *fds=(int*)CMSG_DATA(c);
   for(size_t i=0;i<k;i++){if(count++==0)received=fds[i];else close(fds[i]);}
  }
 }
 if(n>0&&n<(ssize_t)sizeof(r)&&!io((char*)&r+n,sizeof(r)-(size_t)n,0))n=sizeof(r);
 int valid=n==sizeof(r)&&!(msg.msg_flags&(MSG_CTRUNC|MSG_TRUNC))&&r.magic==MAGIC&&!r.bytes;
 if(valid&&r.result==801&&count==0)return;
 struct stat st;int seals=received<0?-1:fcntl(received,F_GET_SEALS);
 if(!valid||r.result||count!=1||fstat(received,&st)||!S_ISREG(st.st_mode)||st.st_size!=2*BULK_BYTES||
    seals<0||(seals&(F_SEAL_GROW|F_SEAL_SHRINK|F_SEAL_SEAL))!=(F_SEAL_GROW|F_SEAL_SHRINK|F_SEAL_SEAL)){
  if(received>=0)close(received);fail();return;
 }
 void *mapped=mmap(NULL,2*BULK_BYTES,PROT_READ|PROT_WRITE,MAP_SHARED,received,0);close(received);
 if(mapped==MAP_FAILED){fail();return;}bulk=mapped;
}
static int bulk_request(const void *in,size_t n,const void *payload,void *out,size_t cap,size_t *got){
 uint32_t kind,reserved;uint64_t bytes;
 if(n<48)return -1;
 memcpy(&kind,in,4);memcpy(&reserved,(const char*)in+4,4);memcpy(&bytes,(const char*)in+40,8);
 if(reserved||bytes<BULK_THRESHOLD||bytes>BULK_BYTES||
    !((kind==1&&n==48+bytes&&!cap)||(kind==2&&n==48&&cap==bytes)))return -1;
 if(!bulk_probed)bulk_negotiate();if(failed)return 999;if(!bulk)return -1;
 if(kind==1)memcpy(bulk,payload?payload:(const char*)in+48,(size_t)bytes);
 struct {uint32_t magic,api;uint64_t bytes,capacity;} q={MAGIC,BULK_COPY,48,cap};
 struct {uint32_t magic,result;uint64_t bytes;} r;
 ++wire_calls;
 if(io(&q,sizeof(q),1)||io((void*)in,48,1)||io(&r,sizeof(r),0)||r.magic!=MAGIC||
    r.bytes>cap||(!r.result&&r.bytes!=cap)||(r.result&&r.bytes)){
  fail();return 999;
 }
 if(r.result){if(r.result==999)fail();return r.result;}
 if(kind==2)memcpy(out,bulk+BULK_BYTES,(size_t)r.bytes);
 *got=r.bytes;return 0;
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
 negotiated=1;
 const char *math=getenv("VMWEAVE_BLAS_MATH_CACHE");
 math_cache_enabled=math&&!strcmp(math,"1");
 const char *enabled=vmweave_getenv("VMWEAVE_STATE_CACHE");
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
static int exchange_impl(uint32_t api,const void *in,size_t n,const void *payload,void *out,size_t cap,size_t *got){
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
 /* Never bypass session health or the inherited-process fence. A peer without
  * the existing state-cache lease capability always receives every setter. */
 int math_request=cache_enabled&&math_cache_enabled&&api==BLAS_MATH_SET&&n==12;
 if(math_request){
  if(math_match(in)){++math_hits;result=0;goto done;}
  ++math_misses;
 }
 /* Conservatively clear all entries even if create/destroy subsequently fails. */
 if(api==BLAS_CREATE||api==BLAS_DESTROY)invalidate_math();
 if(cache_enabled&&!n){
  if(api==GET_DEVICE&&have_device&&cap>=4){memcpy(out,device,4);*got=4;++device_hits;result=0;goto done;}
  if(api==PRIMARY_STATE&&have_primary&&cap>=8){memcpy(out,primary,8);*got=8;++primary_hits;result=0;goto done;}
 }
 if(api==SET_DEVICE||api==2)invalidate();
 result=api==0x1012u?bulk_request(in,n,payload,out,cap,got):-1;
 if(result==-1){
  if(payload){
   /* No CUDA request has been sent: capability fallback may materialize payload. */
   unsigned char *joined=malloc(n);
   if(!joined){result=2;}else{
    memcpy(joined,in,48);memcpy(joined+48,payload,n-48);
    result=request(api,joined,n,out,cap,got);free(joined);
   }
  }else result=request(api,in,n,out,cap,got);
 }
 if(result){invalidate();if(result==999&&cache_enabled)fail();goto done;}
 if(cache_enabled&&!n){
  if(api==GET_DEVICE&&*got==4&&!memcmp(out,(unsigned char[4]){0},4)){memcpy(device,out,4);have_device=1;}
  if(api==PRIMARY_STATE&&*got==8){int active;memcpy(&active,(char*)out+4,4);
   if(active==1){memcpy(primary,out,8);have_primary=1;}
  }
 }
 if(math_request&&*got==0)remember_math(in);
 if(api==2)fail();
 done:pthread_mutex_unlock(&lock);return result;
}
static pthread_once_t direct_once=PTHREAD_ONCE_INIT;
static int direct_enabled;
static void direct_configure(void){
 const char *v=getenv("VMWEAVE_BULK_DIRECT"),*enabled=getenv("VMWEAVE_BULK_COPY");
 direct_enabled=v&&!strcmp(v,"1")&&enabled&&!strcmp(enabled,"1");
}
int vmweave_broker_direct_enabled(void){pthread_once(&direct_once,direct_configure);return direct_enabled;}
int vmweave_broker_exchange(uint32_t api,const void *in,size_t n,void *out,size_t cap,size_t *got){
 return exchange_impl(api,in,n,NULL,out,cap,got);
}
int vmweave_broker_copy_direct(const void *descriptor,const void *payload,size_t bytes,size_t *got){
 if(!descriptor||!payload||!got||bytes<BULK_THRESHOLD||bytes>BULK_BYTES)return 1;
 uint32_t kind,reserved;uint64_t encoded;
 memcpy(&kind,descriptor,4);memcpy(&reserved,(const char*)descriptor+4,4);memcpy(&encoded,(const char*)descriptor+40,8);
 if(kind!=1||reserved||encoded!=bytes)return 1;
 return exchange_impl(0x1012u,descriptor,48+bytes,payload,NULL,0,got);
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

/* Separate diagnostic ABI preserves the existing six state-cache counters.
 * enabled, hits, misses (forwarded eligible setters), invalidations, full. */
void vmweave_broker_math_cache_stats(uint64_t out[5]){
 if(!out)return;
 pid_t unset=0;atomic_compare_exchange_strong(&owner,&unset,getpid());
 if(owner!=getpid()){memset(out,0,5*sizeof(*out));return;}
 pthread_mutex_lock(&lock);
 out[0]=cache_enabled&&math_cache_enabled;out[1]=math_hits;out[2]=math_misses;
 out[3]=math_invalidations;out[4]=math_full;
 pthread_mutex_unlock(&lock);
}
