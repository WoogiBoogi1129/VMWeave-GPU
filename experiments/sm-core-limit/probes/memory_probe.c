#include <cuda.h>
#include <stdio.h>
int main(void){
 CUdevice d;CUcontext c;CUdeviceptr p;
 if(cuInit(0)||cuDeviceGet(&d,0)||cuCtxCreate_v2(&c,0,d))return 1;
 CUresult small=cuMemAlloc(&p,16*1024*1024);
 if(small!=CUDA_SUCCESS)return 2;
 if(cuMemFree(p)!=CUDA_SUCCESS)return 3;
 CUresult over=cuMemAlloc(&p,(size_t)3*1024*1024*1024);
 if(over==CUDA_SUCCESS)cuMemFree(p);
 printf("{\"small_allocation\":%d,\"over_quota\":%d,\"expected_over_quota\":%d}\n",small,over,CUDA_ERROR_OUT_OF_MEMORY);
 cuCtxDestroy(c);
 return over==CUDA_ERROR_OUT_OF_MEMORY?0:4;
}
