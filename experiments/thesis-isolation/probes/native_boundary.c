/* Native CUDA context control. Only controller-paired synthetic allocations;
 * no discovery, IPC import/export, or memory scanning. */
#define _POSIX_C_SOURCE 200809L
#include <cuda.h>
#include <cuda_runtime_api.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>

static const char ptx[]=".version 7.0\n.target sm_70\n.address_size 64\n"
".visible .entry wr(.param .u64 p,.param .u32 v){.reg .u64 %p;.reg .u32 %v;ld.param.u64 %p,[p];ld.param.u32 %v,[v];st.global.u32 [%p],%v;ret;}\n"
".visible .entry rd(.param .u64 p,.param .u64 o){.reg .u64 %p,%o;.reg .u32 %v;ld.param.u64 %p,[p];ld.param.u64 %o,[o];ld.global.u32 %v,[%p];st.global.u32 [%o],%v;ret;}\n";
static int loaded(const char *needle){char line[4096];FILE *f=fopen("/proc/self/maps","r");if(!f)return 0;int found=0;while(fgets(line,sizeof(line),f))if(strstr(line,needle))found=1;fclose(f);return found;}
#define CHECK(x) do{int err=(int)(x);if(err){printf("{\"event\":\"init_error\",\"line\":%d,\"code\":%d}\n",__LINE__,err);return 1;}}while(0)
int main(int argc,char **argv){
 setvbuf(stdout,NULL,_IOLBF,0);
 if(argc!=3||getenv("CUDA_MPS_PIPE_DIRECTORY"))return 2;
 unsigned seed=(unsigned)strtoul(argv[1],NULL,10),expected[1024],observed[1024];
 int count=0;CHECK(cudaGetDeviceCount(&count));if(count!=1||!loaded("libvgpu.so")||loaded("libflyt_guest"))return 2;
 CHECK(cudaSetDevice(0));struct cudaDeviceProp prop;CHECK(cudaGetDeviceProperties(&prop,0));
 const unsigned char *u=(const unsigned char*)prop.uuid.bytes;char uuid[41];
 snprintf(uuid,sizeof(uuid),"GPU-%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",u[0],u[1],u[2],u[3],u[4],u[5],u[6],u[7],u[8],u[9],u[10],u[11],u[12],u[13],u[14],u[15]);
 if(strcmp(uuid,argv[2]))return 2;
 size_t free_bytes=0,total=0;CHECK(cudaMemGetInfo(&free_bytes,&total));if(!total||total>2048ull*1024*1024)return 2;
 void *mem=NULL,*out=NULL;CHECK(cudaMalloc(&mem,sizeof(expected)));CHECK(cudaMalloc(&out,sizeof(expected)));
 for(unsigned i=0;i<1024;i++)expected[i]=seed+i*2654435761u;
 CHECK(cudaMemcpy(mem,expected,sizeof(expected),cudaMemcpyHostToDevice));
 CUmodule module;CUfunction rd,wr;CUcontext context=NULL;CUdeviceptr base=0;size_t bytes=0;
 CHECK(cuModuleLoadData(&module,ptx));CHECK(cuModuleGetFunction(&rd,module,"rd"));CHECK(cuModuleGetFunction(&wr,module,"wr"));
 CHECK(cuCtxGetCurrent(&context));CHECK(cuMemGetAddressRange(&base,&bytes,(CUdeviceptr)(uintptr_t)mem));
 if(!context||base!=(CUdeviceptr)(uintptr_t)mem||bytes<sizeof(expected))return 2;
 printf("{\"event\":\"ready\",\"pid\":%ld,\"gpu\":\"%s\",\"context\":\"%p\",\"address\":%llu,\"bytes\":4096,\"mapping_base\":%llu,\"mapping_bytes\":%zu,\"output_address\":%llu,\"seed\":%u,\"quota_visible_bytes\":%zu,\"hami_loaded\":true,\"guest_shim_loaded\":false}\n",(long)getpid(),uuid,(void*)context,(unsigned long long)(uintptr_t)mem,(unsigned long long)base,bytes,(unsigned long long)(uintptr_t)out,seed,total);
 char line[128],op[32];unsigned sequence=0;unsigned long long target=0;int poisoned=0;
 while(fgets(line,sizeof(line),stdin)){
  op[0]=0;target=0;if(sscanf(line,"%31s %llu",op,&target)<1)continue;
  if(!strcmp(op,"quit"))break;
  if(poisoned){printf("{\"event\":\"poisoned\"}\n");break;}
  ++sequence;
  if(!strcmp(op,"check")){
   int code=(int)cudaMemcpy(observed,mem,sizeof(observed),cudaMemcpyDeviceToHost);unsigned different=0;
   if(!code)for(unsigned i=0;i<1024;i++)different+=observed[i]!=expected[i];
   printf("{\"event\":\"check\",\"sequence\":%u,\"code\":%d,\"mismatches\":%u}\n",sequence,code,different);
  }else if(!strcmp(op,"mapping")){
   CUdeviceptr b=0;size_t n=0;int code=(int)cuMemGetAddressRange(&b,&n,(CUdeviceptr)target);
   int own=(target>=(uintptr_t)mem&&target-(uintptr_t)mem<4096)||(target>=(uintptr_t)out&&target-(uintptr_t)out<4096);
   printf("{\"event\":\"mapping\",\"sequence\":%u,\"target\":%llu,\"code\":%d,\"base\":%llu,\"bytes\":%zu,\"own_buffer_alias\":%s,\"gpu_access_issued\":false}\n",sequence,target,code,(unsigned long long)b,n,own?"true":"false");
  }else if(!strcmp(op,"read")||!strcmp(op,"write")){
   /* Preparation stage deliberately exposes only own-buffer kernel operations. */
   int read=!strcmp(op,"read");unsigned sentinel=0xa5a5a5a5u,value=seed^0x5a5a5a5au,result=sentinel;
   int prep=read?(int)cudaMemcpy(out,&sentinel,4,cudaMemcpyHostToDevice):0;
   CUdeviceptr p=(uintptr_t)mem,o=(uintptr_t)out;void *params[]={&p,read?(void*)&o:(void*)&value};
   CUcontext current=NULL;int ctx=(int)cuCtxGetCurrent(&current);
   printf("{\"event\":\"launch_begin\",\"sequence\":%u,\"context\":\"%p\",\"context_query\":%d,\"target\":%llu,\"own_buffer\":true}\n",sequence,(void*)current,ctx,(unsigned long long)p);
   int launch=prep?prep:(ctx?ctx:(int)cuLaunchKernel(read?rd:wr,1,1,1,1,1,1,0,0,params,NULL));
   int sync=launch?-1:(int)cudaDeviceSynchronize();
   int copy=(launch||sync)?-1:(int)cudaMemcpy(&result,read?out:mem,4,cudaMemcpyDeviceToHost);
   if(!read&&!launch&&!sync&&!copy)expected[0]=value;
   printf("{\"event\":\"access\",\"op\":\"%s\",\"sequence\":%u,\"prep\":%d,\"launch\":%d,\"sync\":%d,\"copy\":%d,\"observed\":%u,\"expected\":%u}\n",op,sequence,prep,launch,sync,copy,result,expected[0]);
   if(launch||sync||copy)poisoned=1;
  }else{printf("{\"event\":\"unsupported_command\"}\n");return 2;}
  printf("{\"event\":\"done\",\"op\":\"%s\",\"sequence\":%u}\n",op,sequence);
 }
 if(poisoned)return 1;
 CHECK(cuModuleUnload(module));CHECK(cudaFree(out));CHECK(cudaFree(mem));return 0;
}
