#include <assert.h>
#include <cuda.h>
#include <cuda_runtime_api.h>
#include <stdio.h>
CUresult cuDeviceGet(CUdevice *d,int ordinal){*d=ordinal;return CUDA_SUCCESS;}
static int captures=0,records=0,launches=0;
cudaError_t cudaStreamIsCapturing(cudaStream_t s,enum cudaStreamCaptureStatus *v){*v=captures?cudaStreamCaptureStatusActive:cudaStreamCaptureStatusNone;return cudaSuccess;}
cudaError_t cudaEventRecord(cudaEvent_t e,cudaStream_t s){records++;return cudaSuccess;}
cudaError_t cudaLaunchKernel(const void *f,dim3 g,dim3 b,void **a,size_t m,cudaStream_t s){launches++;return cudaSuccess;}
extern cudaError_t cudaStreamGetCaptureInfo_v2(cudaStream_t,enum cudaStreamCaptureStatus*,unsigned long long*,cudaGraph_t*,const cudaGraphNode_t**,size_t*);
int main(void){
 void *p=(void*)1;enum cudaDriverEntryPointQueryResult st;
 assert(cudaGetDriverEntryPointByVersion("cuDeviceGet",&p,12080,0,&st)==cudaSuccess);
 assert(p==(void*)cuDeviceGet && st==cudaDriverEntryPointSuccess);
 CUdevice d=-1;assert(((CUresult(*)(CUdevice*,int))p)(&d,7)==CUDA_SUCCESS && d==7);
 assert(cudaGetDriverEntryPointByVersion("cuDeviceGet",&p,1000,0,&st)==cudaSuccess && !p && st==cudaDriverEntryPointVersionNotSufficent);
 assert(cudaGetDriverEntryPointByVersion("noSuchAPI",&p,12080,0,&st)==cudaSuccess && !p && st==cudaDriverEntryPointSymbolNotFound);
 assert(cudaGetDriverEntryPointByVersion("cuDeviceGet",&p,99999,0,&st)==cudaErrorNotSupported && !p);
 assert(cudaGetDriverEntryPointByVersion("cuDeviceGet",&p,12080,8,&st)==cudaErrorInvalidValue && !p);
 assert(cudaGetDriverEntryPointByVersion(NULL,&p,12080,0,&st)==cudaErrorInvalidValue);
 assert(cudaGetDriverEntryPointByVersion("cuDeviceGet",NULL,12080,0,&st)==cudaErrorInvalidValue);
 assert(cudaGetDriverEntryPoint("cuDeviceGet",&p,0,NULL)==cudaSuccess && p);
 enum cudaStreamCaptureStatus cs;unsigned long long id=9;size_t count=9;
 assert(cudaStreamGetCaptureInfo_v2(0,&cs,&id,NULL,NULL,&count)==cudaSuccess && cs==cudaStreamCaptureStatusNone && id==0 && count==0);
 captures=1;assert(cudaStreamGetCaptureInfo_v2(0,&cs,NULL,NULL,NULL,NULL)==cudaErrorNotSupported);
 assert(cudaEventRecordWithFlags(0,0,1)==cudaErrorNotSupported && records==0);
 assert(cudaEventRecordWithFlags(0,0,0)==cudaSuccess && records==1);
 cudaLaunchConfig_t config={0};config.numAttrs=1;
 assert(cudaLaunchKernelExC(&config,(void*)1,NULL)==cudaErrorNotSupported && launches==0);
 config.numAttrs=0;assert(cudaLaunchKernelExC(&config,(void*)1,NULL)==cudaSuccess && launches==1);
 assert(cudaGraphDebugDotPrint(0,"/tmp/unused",0)==cudaErrorNotSupported);
 puts("PASS entrypoint/query status, ABI pointer call, unsupported flags/version/graphs, capture and launch forwarding");
}
