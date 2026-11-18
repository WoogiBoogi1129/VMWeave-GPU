/* Same operations and timing boundaries on N/V/F/L. Setup-only link adapters. */
#include <cuda.h>
#include <cuda_runtime_api.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#define CK(x) do { int e=(int)(x); if(e){fprintf(stderr,"CUDA_FAILURE %s=%d\n",#x,e);exit(10);} }while(0)
#define MAX_BYTES (64u*1024u*1024u)
#define CAPACITY 16000000u
static uint64_t ns(clockid_t c){struct timespec t;clock_gettime(c,&t);return (uint64_t)t.tv_sec*1000000000ull+t.tv_nsec;}
static CUfunction fn;static void *device,*state;static unsigned char *input,*output;
static CUdeviceptr stateptr;static uint32_t sequence=0;static uint64_t launches=0;
static int condition;static size_t bytes;static unsigned batch;
static void op(void){
 if(condition==1){CK(cudaMemcpy(device,input,bytes,cudaMemcpyHostToDevice));}
 else if(condition==2){CK(cudaMemcpy(output,device,bytes,cudaMemcpyDeviceToHost));}
 else {for(unsigned k=0;k<batch;k++){sequence++;void *args[]={&stateptr,&sequence};CK(cuLaunchKernel(fn,1,1,1,1,1,1,0,NULL,args,NULL));launches++;}}
 CK(cudaDeviceSynchronize());
}
static void verify(void){
 if(condition==1||condition==2){if(condition==1){CK(cudaMemcpy(output,device,bytes,cudaMemcpyDeviceToHost));CK(cudaDeviceSynchronize());}if(memcmp(input,output,bytes)){fprintf(stderr,"INCORRECT buffer %zu\n",bytes);exit(11);}}
 else {uint32_t actual[2];CK(cudaMemcpy(actual,state,8,cudaMemcpyDeviceToHost));CK(cudaDeviceSynchronize());if(actual[0]!=(uint32_t)(launches*19)||actual[1]!=sequence){fprintf(stderr,"INCORRECT kernel %u %u expected %u %u\n",actual[0],actual[1],(uint32_t)(launches*19),sequence);exit(11);}}
}
int main(int argc,char **argv){
 /* module output-directory order(comma IDs) duration seconds warm seconds pilot(0/1) */
 if(argc!=7)return 2;
 double duration=atof(argv[4]),warm=atof(argv[5]);int pilot=atoi(argv[6]);
 if(duration<=0||duration>30||warm<0||warm>10)return 2;
#ifdef FLYT_TCP
 extern int connection_is_local,shm_enabled,socktype;
 printf("{\"event\":\"TRANSPORT\",\"socktype\":%d,\"connection_is_local\":%d,\"shm_enabled\":%d}\n",socktype,connection_is_local,shm_enabled);
 if(socktype!=1||connection_is_local!=0)return 9;
#endif
 uint64_t *samples=calloc(CAPACITY,sizeof(uint64_t));input=malloc(MAX_BYTES);output=malloc(MAX_BYTES);
 if(!samples||!input||!output)return 3;
 for(size_t i=0;i<CAPACITY;i+=512)samples[i]=0;
 uint32_t rng=20261117;for(size_t i=0;i<MAX_BYTES;i++){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;input[i]=(unsigned char)rng;output[i]=0;}
 int count;CK(cudaGetDeviceCount(&count));if(count!=1){fprintf(stderr,"device count %d\n",count);return 4;}CK(cudaSetDevice(0));
 CK(cudaMalloc(&device,MAX_BYTES));CK(cudaMalloc(&state,8));uint32_t zero[2]={0,0};CK(cudaMemcpy(state,zero,8,cudaMemcpyHostToDevice));stateptr=(CUdeviceptr)(uintptr_t)state;
 FILE *f=fopen(argv[1],"rb");if(!f)return 5;fseek(f,0,SEEK_END);long len=ftell(f);rewind(f);void *code=calloc(len+1,1);if(fread(code,1,len,f)!=(size_t)len)return 5;fclose(f);
 CUmodule module;CK(cuModuleLoadData(&module,code));CK(cuModuleGetFunction(&fn,module,"comm_sequence"));free(code);
#ifdef VMWEAVE
 extern int vmweaveRegisterKernelABI(CUfunction,unsigned,const unsigned char*,const unsigned char*);
 const unsigned char arg_sizes[]={8,4},pointers[]={1,0};CK(vmweaveRegisterKernelABI(fn,2,arg_sizes,pointers));
#endif
 uint64_t timer_min=UINT64_MAX;for(int i=0;i<10000;i++){uint64_t a=ns(CLOCK_MONOTONIC),d=ns(CLOCK_MONOTONIC)-a;if(d<timer_min)timer_min=d;}
 printf("{\"event\":\"SETUP\",\"pid\":%d,\"timer_min_ns\":%lu,\"device_count\":%d,\"input_seed\":20261117}\n",getpid(),timer_min,count);fflush(stdout);
 const size_t sizes[]={4,4096,65536,1048576,16777216,67108864};
 char *order=strdup(argv[3]),*save=NULL;
 for(char *s=strtok_r(order,",",&save);s;s=strtok_r(NULL,",",&save)){
  int id=atoi(s);if(id<0||id>15)return 2;
  condition=id>=1&&id<=12?(id<=6?1:2):0;bytes=condition?sizes[(id-1)%6]:8;batch=id==0?1:id==13?10:id==14?100:1000;
  CK(cudaMemcpy(device,input,bytes,cudaMemcpyHostToDevice));CK(cudaDeviceSynchronize());
  if(condition){CK(cudaMemcpy(output,device,bytes,cudaMemcpyDeviceToHost));CK(cudaDeviceSynchronize());verify();}else{op();verify();}
  printf("{\"event\":\"WARMUP_START\",\"id\":%d,\"utc_ns\":%lu}\n",id,ns(CLOCK_REALTIME));fflush(stdout);
  uint64_t t=ns(CLOCK_MONOTONIC),n=0;do{op();n++;}while(n<10||(!pilot&&(ns(CLOCK_MONOTONIC)-t)<(uint64_t)(warm*1e9)));
  verify();
  printf("{\"event\":\"START\",\"id\":%d,\"utc_ns\":%lu}\n",id,ns(CLOCK_REALTIME));fflush(stdout);
  uint64_t cpu0=ns(CLOCK_PROCESS_CPUTIME_ID),utc0=ns(CLOCK_REALTIME);t=ns(CLOCK_MONOTONIC);n=0;
  do {if(n==CAPACITY){fprintf(stderr,"SAMPLE_CAPACITY\n");return 6;}uint64_t a=ns(CLOCK_MONOTONIC);op();samples[n++]=ns(CLOCK_MONOTONIC)-a;}while(pilot?n<30:(ns(CLOCK_MONOTONIC)-t)<(uint64_t)(duration*1e9));
  uint64_t elapsed=ns(CLOCK_MONOTONIC)-t,cpu=ns(CLOCK_PROCESS_CPUTIME_ID)-cpu0,utc1=ns(CLOCK_REALTIME);
  verify();
  char path[1024];snprintf(path,sizeof(path),"%s/c%02d.u64",argv[2],id);f=fopen(path,"wb");if(!f||fwrite(samples,8,n,f)!=n)return 7;fclose(f);
  printf("{\"event\":\"RESULT\",\"id\":%d,\"direction\":\"%s\",\"bytes\":%zu,\"K\":%u,\"completed\":%lu,\"elapsed_ns\":%lu,\"client_cpu_ns\":%lu,\"start_utc_ns\":%lu,\"end_utc_ns\":%lu,\"final_sequence\":%u,\"total_launches\":%lu,\"correctness\":\"PASS\",\"raw_format\":\"little-endian uint64 nanoseconds\"}\n",id,condition==1?"H2D":condition==2?"D2H":"kernel",bytes,condition?0:batch,n,elapsed,cpu,utc0,utc1,sequence,launches);fflush(stdout);
 }
 CK(cuModuleUnload(module));CK(cudaFree(state));CK(cudaFree(device));free(samples);free(input);free(output);free(order);return 0;
}
