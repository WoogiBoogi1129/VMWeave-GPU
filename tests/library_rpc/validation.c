/* CPU-only descriptor and malformed-wire checks against real cuDNN descriptors. */
#include "vmweave_library.h"
#include <cudnn.h>
#include <cublasLt.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
void *vmweave_compat_blas(uint64_t id){(void)id;return NULL;}
void *vmweave_compat_dnn(uint64_t id){(void)id;return NULL;}
int vmweave_async_stream(uint64_t id,void **p){if(id)return 0;*p=NULL;return 1;}
int vmweave_async_stream_id(void *p,uint64_t *id){if(p)return 0;*id=0;return 1;}
int vmweave_cuda_exec_resolve(struct vmweave_cuda_exec *x,struct vmweave_device_ref r,size_t n,void **p){(void)x;(void)r;(void)n;(void)p;assert(!"unexpected GPU pointer resolution");return 0;}
static uint8_t p[VMWEAVE_LIBRARY_REQUEST],out[VMWEAVE_LIBRARY_RESPONSE];
static struct vmweave_shm_response response;
static int invoke(unsigned api,size_t n){struct vmweave_shm_request q={0};q.api_id=api;q.payload_schema=1;q.input=p;q.input_bytes=n;memset(&response,0,sizeof(response));response.output=out;response.output_capacity=sizeof(out);vmweave_library_dispatch(NULL,&q,&response);return response.api_result;}
#define SET(i,v) vmweave_put(p+8*(i),v,8)
#define CALL(api) invoke(api,sizeof(p))
int main(void){
 invoke(VMWEAVE_LIB_cudnnCreateTensorDescriptor,sizeof(p)-1);assert(response.transport_status==VMWEAVE_SHM_BAD_DESCRIPTOR);
 assert(CALL(VMWEAVE_LIB_cudnnCreateTensorDescriptor)==0);uint64_t id=vmweave_get(out,8);assert(id);
 SET(0,id);SET(1,CUDNN_DATA_FLOAT);SET(2,3);SET(3,2);SET(4,3);SET(5,4);SET(11,12);SET(12,4);SET(13,1);
 assert(CALL(VMWEAVE_LIB_cudnnSetTensorNdDescriptor)==0);
 SET(1,3);assert(CALL(VMWEAVE_LIB_cudnnGetTensorNdDescriptor)==0);assert(vmweave_get(out+8,8)==3&&vmweave_get(out+16,8)==2&&vmweave_get(out+24,8)==3);
 SET(1,9);assert(CALL(VMWEAVE_LIB_cudnnGetTensorNdDescriptor)==CUDNN_STATUS_BAD_PARAM);
 assert(CALL(VMWEAVE_LIB_cudnnDestroyRNNDescriptor)==CUDNN_STATUS_BAD_PARAM); /* wrong handle type */
 assert(CALL(VMWEAVE_LIB_cudnnDestroyTensorDescriptor)==0);
 assert(CALL(VMWEAVE_LIB_cudnnDestroyTensorDescriptor)==CUDNN_STATUS_BAD_PARAM); /* stale handle */
 SET(0,0);assert(CALL(VMWEAVE_LIB_cudnnSetStream)==CUDNN_STATUS_BAD_PARAM);
 assert(CALL(VMWEAVE_LIB_cublasLtDestroy)==CUBLAS_STATUS_INVALID_VALUE);
 assert(CALL(VMWEAVE_LIB_cudnnCreateRNNDataDescriptor)==0);id=vmweave_get(out,8);SET(0,id);SET(1,CUDNN_DATA_DOUBLE);SET(4,16);assert(CALL(VMWEAVE_LIB_cudnnSetRNNDataDescriptor)==CUDNN_STATUS_NOT_SUPPORTED);
 SET(1,CUDNN_DATA_FLOAT);SET(4,1025);assert(CALL(VMWEAVE_LIB_cudnnSetRNNDataDescriptor)==CUDNN_STATUS_NOT_SUPPORTED);
 assert(vmweave_library_close()==0);assert(CALL(VMWEAVE_LIB_cudnnDestroyRNNDataDescriptor)==CUDNN_STATUS_BAD_PARAM);
 puts("PASS: malformed packets, descriptor round-trip, wrong/stale handles, unsupported types, cleanup");
}
