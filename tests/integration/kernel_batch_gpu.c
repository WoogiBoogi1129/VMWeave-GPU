/* Run only in an isolated VMWeave GPU session. The qualification PTX computes
 * state[0] = state[0] * 1664525 + sequence (mod 2^32), then stores sequence in
 * state[1]. This order-sensitive checksum detects internal reordering too. */
#include <cuda.h>
#include <cuda_runtime_api.h>
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#define CK(x) do{int e=(x);if(e){fprintf(stderr,"%s=%d\n",#x,e);return 10;}}while(0)
extern int vmweaveRegisterKernelABI(CUfunction,unsigned,const unsigned char*,const unsigned char*);
static uint32_t expected(unsigned n){uint32_t x=0;for(unsigned i=1;i<=n;i++)x=x*1664525u+i;return x;}
int main(int argc,char **argv){
    if(argc!=3)return 2;
    FILE *f=fopen(argv[1],"rb");assert(f);fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);
    char *ptx=calloc(n+1,1);assert(ptx&&fread(ptx,1,n,f)==(size_t)n);fclose(f);
    int count;CK(cudaGetDeviceCount(&count));assert(count==1);CK(cudaSetDevice(0));
    CUmodule module;CUfunction fn;CK(cuModuleLoadData(&module,ptx));free(ptx);
    CK(cuModuleGetFunction(&fn,module,"comm_sequence"));
    unsigned char sizes[]={8,4},pointers[]={1,0};CK(vmweaveRegisterKernelABI(fn,2,sizes,pointers));
    void *state;CK(cudaMalloc(&state,8));uint32_t host[2]={0,0};CK(cudaMemcpy(state,host,8,cudaMemcpyHostToDevice));
    CUdeviceptr pointer=(CUdeviceptr)(uintptr_t)state;uint32_t seq=0;void *args[]={&pointer,&seq};
    if(!strcmp(argv[2],"error")){
        int launch=cuLaunchKernel(fn,1,1,1,0,1,1,0,0,args,0);
        int sync=cudaDeviceSynchronize();int next=cuLaunchKernel(fn,1,1,1,1,1,1,0,0,args,0);
        assert((!launch||launch==sync)&&sync!=0&&next==sync);
        printf("PASS: asynchronous CUDA error propagated, terminal session, code=%d\n",sync);return 0;
    }
    for(seq=1;seq<=1003;seq++)CK(cuLaunchKernel(fn,1,1,1,1,1,1,0,0,args,0));
    seq=0xdeadbeef; /* Caller storage must not be retained by buffered launches. */
    if(!strcmp(argv[2],"kill")){raise(SIGKILL);return 99;}
    CK(cudaMemcpy(host,state,8,cudaMemcpyDeviceToHost));
    assert(host[0]==expected(1003)&&host[1]==1003);
    for(seq=1004;seq<=1010;seq++)CK(cuLaunchKernel(fn,1,1,1,1,1,1,0,0,args,0));
    CK(cudaStreamSynchronize(0));CK(cudaMemcpy(host,state,8,cudaMemcpyDeviceToHost));
    assert(host[0]==expected(1010)&&host[1]==1010);
    void *big;CK(cudaMalloc(&big,2*1024*1024));void *input=calloc(2*1024*1024,1);assert(input);
    seq=1011;CK(cuLaunchKernel(fn,1,1,1,1,1,1,0,0,args,0));
    /* Large direct H2D must not overtake the pending kernel. */
    CK(cudaMemcpy(big,input,2*1024*1024,cudaMemcpyHostToDevice));
    CK(cudaMemcpy(host,state,8,cudaMemcpyDeviceToHost));assert(host[0]==expected(1011)&&host[1]==1011);
    seq=1012;CK(cuLaunchKernel(fn,1,1,1,1,1,1,0,0,args,0));CK(cuModuleUnload(module));
    CK(cudaMemcpy(host,state,8,cudaMemcpyDeviceToHost));assert(host[0]==expected(1012)&&host[1]==1012);
    CK(cudaFree(big));CK(cudaFree(state));free(input);
    puts("PASS: GPU sequence/argument snapshot, >128 launches, D2H, stream sync, direct H2D, module unload");return 0;
}
