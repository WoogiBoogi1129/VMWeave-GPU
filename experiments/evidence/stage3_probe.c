/* Stage 3: interactive commands keep the same process/session across expected OOM.
 * Checks first and last 1 MiB of a live allocation, not every byte of 1.5 GiB.
 * The host sends phase commands over stdin; stdout is line-buffered JSONL.
 */
#include <cuda.h>
#include <cuda_runtime_api.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <poll.h>
#define N 262144u
#define MIB 1048576ull
extern int flytRegisterKernelABI(CUfunction,unsigned,const unsigned char*,const unsigned char*);
static char role;static unsigned seed,completed,mismatch_total;static size_t live;
static void *mem;static CUmodule module;static CUfunction fn;
static uint32_t in[N],out[N],tail[N];
static double clk(clockid_t id){struct timespec t;clock_gettime(id,&t);return t.tv_sec+t.tv_nsec/1e9;}
static void prefix(const char *event){printf("{\"event\":\"%s\",\"vm\":\"%c\",\"pid\":%d,\"utc_seconds\":%.9f,\"monotonic_seconds\":%.9f,\"live_allocated_bytes\":%zu",event,role,getpid(),clk(CLOCK_REALTIME),clk(CLOCK_MONOTONIC),live);}
static void check(int e,const char *api){if(e){prefix("FAIL");printf(",\"api\":\"%s\",\"api_result\":%d}\n",api,e);exit(10);}}
#define OK(x) check((int)(x),#x)
static const char ptx[]=".version 7.0\n.target sm_70\n.address_size 64\n.visible .entry add19(.param .u64 ptr){\n.reg .u64 %p,%off; .reg .u32 %i,%t,%b,%r;\nld.param.u64 %p,[ptr];mov.u32 %t,%tid.x;mov.u32 %b,%ctaid.x;mad.lo.u32 %i,%b,256,%t;mul.wide.u32 %off,%i,4;add.u64 %p,%p,%off;ld.global.u32 %r,[%p];add.u32 %r,%r,19;st.global.u32 [%p],%r;ret;}\n";
static void info(const char *phase){size_t free_b=0,total=0;OK(cudaMemGetInfo(&free_b,&total));prefix("MEMINFO");printf(",\"phase\":\"%s\",\"free_bytes\":%zu,\"total_bytes\":%zu}\n",phase,free_b,total);}
static void tick(void){
 for(unsigned i=0;i<N;i++)in[i]=seed+i+completed;
 OK(cudaMemcpy(mem,in,MIB,cudaMemcpyHostToDevice));
 CUdeviceptr p=(CUdeviceptr)(uintptr_t)mem;void *args[]={&p};OK(cuLaunchKernel(fn,1024,1,1,256,1,1,0,NULL,args,NULL));OK(cudaDeviceSynchronize());
 OK(cudaMemcpy(out,mem,MIB,cudaMemcpyDeviceToHost));unsigned wrong=0;
 for(unsigned i=0;i<N;i++)if(out[i]!=in[i]+19u)wrong++;
 OK(cudaMemcpy(out,(char*)mem+live-MIB,MIB,cudaMemcpyDeviceToHost));
 for(unsigned i=0;i<N;i++)if(out[i]!=tail[i])wrong++;
 completed++;mismatch_total+=wrong;prefix("PROGRESS");printf(",\"completed\":%u,\"checked_elements\":%u,\"mismatches\":%u,\"guest_pointer\":%llu}\n",completed,2*N,wrong,(unsigned long long)(uintptr_t)mem);
 if(wrong)exit(11);
}
static int allocate(size_t bytes,const char *phase){
 if(mem)exit(12);int e=(int)cudaMalloc(&mem,bytes);if(!e)live=bytes;
 prefix("ALLOC");printf(",\"phase\":\"%s\",\"requested_bytes\":%zu,\"api_result\":%d,\"guest_pointer\":%llu}\n",phase,bytes,e,(unsigned long long)(uintptr_t)mem);
 if(!e){OK(cudaMemcpy((char*)mem+live-MIB,tail,MIB,cudaMemcpyHostToDevice));tick();}
 return e;
}
static void release(const char *phase){if(!mem)exit(13);
 if(!strcmp(phase,"final")){
  const char *names[]={"stage3-output-head.bin","stage3-output-tail.bin"};
  for(int j=0;j<2;j++){OK(cudaMemcpy(out,(char*)mem+(j?live-MIB:0),MIB,cudaMemcpyDeviceToHost));FILE *f=fopen(names[j],"wb");if(!f||fwrite(out,1,MIB,f)!=MIB||fclose(f))exit(14);}
 }
size_t bytes=live;unsigned long long h=(unsigned long long)(uintptr_t)mem;OK(cudaFree(mem));mem=NULL;live=0;prefix("FREE");printf(",\"phase\":\"%s\",\"freed_bytes\":%zu,\"guest_pointer\":%llu,\"api_result\":0}\n",phase,bytes,h);}
int main(int argc,char **argv){
 if(argc!=3 || (argv[1][0]!='A'&&argv[1][0]!='B'))return 2;role=argv[1][0];seed=(unsigned)strtoul(argv[2],0,10);
 setvbuf(stdout,NULL,_IOLBF,0);setvbuf(stdin,NULL,_IONBF,0);alarm(300);
 for(unsigned i=0;i<N;i++)tail[i]=(seed+i)^0xa5a5a5a5u;
 prefix("CONDITIONS");printf(",\"seed\":%u,\"large_bytes\":1610612736,\"small_bytes\":134217728,\"sample_bytes_per_end\":1048576,\"blocks\":1024,\"threads\":256}\n",seed);
 int count=0;OK(cudaGetDeviceCount(&count));if(count!=1)return 3;
 OK(cuModuleLoadData(&module,ptx));OK(cuModuleGetFunction(&fn,module,"add19"));const unsigned char sizes[]={8},ptrs[]={1};OK(flytRegisterKernelABI(fn,1,sizes,ptrs));
 info("before_precheck");OK(allocate(2*MIB,"precheck"));release("precheck");info("ready");prefix("READY");printf("}\n");
 char cmd[32];int large_seen=0,small_seen=0;
 for(;;){struct pollfd fd={.fd=0,.events=POLLIN};int available=poll(&fd,1,1000);if(available<0)return 4;
  if(!available){if(mem)tick();continue;}
  if(!fgets(cmd,sizeof(cmd),stdin))return 5;
  if(!strcmp(cmd,"large\n")){int e=allocate(1536*MIB,"large");large_seen++;if(e!=(role=='A'?cudaErrorMemoryAllocation:cudaSuccess))return 6;info("after_large");}
  else if(!strcmp(cmd,"small\n")){if(role!='A'||large_seen!=1)return 7;OK(allocate(128*MIB,"small"));small_seen++;info("after_small");}
  else if(!strcmp(cmd,"free\n")){tick();release("final");info("after_free");}
  else if(!strcmp(cmd,"exit\n")){if(mem||large_seen!=1||(role=='A'&&small_seen!=1))return 8;break;}
  else return 9;
 }
 OK(cuModuleUnload(module));prefix("RESULT");printf(",\"status\":\"PASS\",\"completed\":%u,\"checked_elements_total\":%llu,\"mismatches\":%u}\n",completed,(unsigned long long)completed*2*N,mismatch_total);return 0;
}
