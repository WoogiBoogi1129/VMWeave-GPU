#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <time.h>
#include <unistd.h>
/* Public CUDA ABI subset implemented by the pinned VMWeave guest library. */
typedef void *CUmodule; typedef void *CUfunction; typedef uint64_t CUdeviceptr;
extern int cudaGetDeviceCount(int*),cudaMalloc(void**,size_t),cudaFree(void*);
extern int cudaMemcpy(void*,const void*,size_t,int);
extern int cuModuleLoadData(CUmodule*,const void*),cuModuleGetFunction(CUfunction*,CUmodule,const char*);
extern int cuLaunchKernel(CUfunction,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,void*,void**,void**);
extern int cuCtxSynchronize(void),cuModuleUnload(CUmodule);
extern int flytRegisterKernelABI(CUfunction,unsigned,const unsigned char*,const unsigned char*);
#define CHECK(x) do {int rc=(x);if(rc){fprintf(stderr,"{\"event\":\"CUDA_ERROR\",\"api\":\"%s\",\"code\":%d}\n",#x,rc);return 1;}}while(0)
static void event(const char*s){struct timespec t;clock_gettime(CLOCK_REALTIME,&t);printf("{\"event\":\"%s\",\"unix_seconds\":%lld.%09ld}\n",s,(long long)t.tv_sec,t.tv_nsec);}
static void terminate(int s){_exit(128+s);}
static const char ptx[]=
".version 7.0\n.target sm_70\n.address_size 64\n"
".visible .entry add_value(.param .u64 ptr,.param .u32 count,.param .u32 value){\n"
".reg .pred %p; .reg .u32 %r<8>; .reg .u64 %rd<4>;\n"
"ld.param.u64 %rd0,[ptr]; ld.param.u32 %r0,[count]; ld.param.u32 %r1,[value];\n"
"mov.u32 %r2,%ctaid.x; mov.u32 %r3,%ntid.x; mov.u32 %r4,%tid.x;\n"
"mad.lo.u32 %r5,%r2,%r3,%r4; setp.ge.u32 %p,%r5,%r0; @%p bra END;\n"
"mul.wide.u32 %rd1,%r5,4; add.u64 %rd2,%rd0,%rd1;\n"
"ld.global.u32 %r6,[%rd2]; add.u32 %r7,%r6,%r1; st.global.u32 [%rd2],%r7;\nEND: ret; }\n";
int main(int argc,char**argv){
 setvbuf(stdout,NULL,_IOLBF,0);signal(SIGTERM,terminate);event("START");
 printf("{\"event\":\"IDENTITY\",\"uid\":%u,\"gid\":%u,\"pid\":%u,\"cpu_fallback\":false}\n",getuid(),getgid(),getpid());
 int count=0;CHECK(cudaGetDeviceCount(&count));if(count!=1)return 2;
 if(argc>1&&!strcmp(argv[1],"--quota")){
   void*p=NULL;size_t bytes=3ULL*1024*1024*1024;int rc=cudaMalloc(&p,bytes);
   printf("{\"event\":\"QUOTA\",\"requested_bytes\":%zu,\"cuda_code\":%d}\n",bytes,rc);
   if(!rc){cudaFree(p);return 3;}return rc==2?0:4;
 }
 const unsigned n=32*1024*1024/sizeof(uint32_t),add=1234567;
 uint32_t*h=malloc((size_t)n*4);if(!h)return 5;
 for(unsigned i=0;i<n;i++)h[i]=i*2654435761U+17;
 void*d=NULL;CHECK(cudaMalloc(&d,(size_t)n*4));
 CHECK(cudaMemcpy(d,h,(size_t)n*4,1));
 CUmodule m;CUfunction f;CHECK(cuModuleLoadData(&m,ptx));CHECK(cuModuleGetFunction(&f,m,"add_value"));
 const unsigned char sizes[]={8,4,4},pointers[]={1,0,0};CHECK(flytRegisterKernelABI(f,3,sizes,pointers));
 CUdeviceptr ptr=(CUdeviceptr)(uintptr_t)d;void*params[]={&ptr,(void*)&n,(void*)&add};
 event("READY_FOR_OBSERVATION");
 if(!(argc>1&&!strcmp(argv[1],"--immediate"))){
   struct timespec pause={0,100000000};int waited=0;
   while(access("/tmp/run",F_OK)){if(++waited>3000){event("HANDSHAKE_TIMEOUT");return 6;}nanosleep(&pause,NULL);}
 }
 CHECK(cuLaunchKernel(f,(n+255)/256,1,1,256,1,1,0,NULL,params,NULL));CHECK(cuCtxSynchronize());event("KERNEL_SYNCHRONIZED");
 CHECK(cudaMemcpy(h,d,(size_t)n*4,2));
 unsigned errors=0;uint64_t checksum=0;
 for(unsigned i=0;i<n;i++){if(h[i]!=(uint32_t)(i*2654435761U+17+add))errors++;checksum+=h[i];}
 CHECK(cuModuleUnload(m));CHECK(cudaFree(d));free(h);
 printf("{\"event\":\"RESULT\",\"elements\":%u,\"mismatches\":%u,\"checksum\":%llu,\"kernel_launches\":1}\n",n,errors,(unsigned long long)checksum);
 event(errors?"FAIL":"PASS");return errors?7:0;
}
