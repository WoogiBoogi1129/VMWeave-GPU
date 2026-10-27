#include <cuda_runtime.h>
#include <stdio.h>
#include <stdlib.h>
#define OK(x) do {cudaError_t e=(x);if(e){fprintf(stderr,"%s error %d\n",#x,(int)e);return 2;}}while(0)
__global__ void verify(const unsigned char *p,size_t n,unsigned char expected,int *bad){
 size_t i=(size_t)blockIdx.x*blockDim.x+threadIdx.x;
 if(i<n&&p[i]!=expected)atomicAdd(bad,1);
}
int main(){
 const size_t n=1048576;unsigned char *p;int *bad,got;cudaStream_t a,b;cudaEvent_t done;
 OK(cudaMalloc(&p,n));OK(cudaMalloc(&bad,sizeof(int)));
 OK(cudaStreamCreate(&a));OK(cudaStreamCreateWithFlags(&b,cudaStreamNonBlocking));OK(cudaEventCreate(&done));
 for(int i=0;i<20;i++){
  // Native default-stream memset must precede the subsequent default-stream kernel.
  OK(cudaMemset(p,0x5a,n));OK(cudaMemset(bad,0,sizeof(int)));
  verify<<<(n+255)/256,256>>>(p,n,0x5a,bad);OK(cudaGetLastError());OK(cudaDeviceSynchronize());
  OK(cudaMemcpy(&got,bad,sizeof(int),cudaMemcpyDeviceToHost));if(got)return 3;
  // Nonblocking stream uses its explicit completion; no implicit cross-stream dependency.
  OK(cudaMemsetAsync(p,0xa5,n,b));OK(cudaMemsetAsync(bad,0,sizeof(int),b));
  verify<<<(n+255)/256,256,0,b>>>(p,n,0xa5,bad);OK(cudaGetLastError());OK(cudaEventRecord(done,b));OK(cudaEventSynchronize(done));
  OK(cudaMemcpy(&got,bad,sizeof(int),cudaMemcpyDeviceToHost));if(got)return 4;
  // A blocking stream must observe the preceding default-stream operation.
  OK(cudaMemset(p,0x3c,n));OK(cudaMemset(bad,0,sizeof(int)));
  verify<<<(n+255)/256,256,0,a>>>(p,n,0x3c,bad);OK(cudaGetLastError());OK(cudaStreamSynchronize(a));
  OK(cudaMemcpy(&got,bad,sizeof(int),cudaMemcpyDeviceToHost));if(got)return 5;
 }
 OK(cudaEventDestroy(done));OK(cudaStreamDestroy(a));OK(cudaStreamDestroy(b));OK(cudaFree(bad));OK(cudaFree(p));
 puts("PASS 60 device verification kernels: native default memset, blocking stream order, explicit nonblocking completion");
}
