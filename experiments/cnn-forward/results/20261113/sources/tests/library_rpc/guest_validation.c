#include "vmweave_guest.h"
#include "vmweave_library.h"
#include <cudnn.h>
#include <cublasLt.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
pthread_mutex_t vmweave_guest_lock=PTHREAD_MUTEX_INITIALIZER;
static int calls,short_reply;
int vmweave_guest_ref(const void *p,size_t bytes,struct vmweave_device_ref *ref){(void)p;(void)bytes;(void)ref;return 1;}
int vmweave_guest_exchange(uint32_t api,const void *input,size_t bytes,void *output,size_t capacity,size_t *received){
 assert(api==VMWEAVE_LIB_cudnnGetRNNTempSpaceSizes);assert(input&&bytes==VMWEAVE_LIBRARY_REQUEST&&capacity==VMWEAVE_LIBRARY_RESPONSE);
 const unsigned char *p=input;assert(vmweave_get(p,8)==1&&vmweave_get(p+8,8)==2&&vmweave_get(p+24,8)==3);
 memset(output,0,capacity);vmweave_put(output,1234,8);vmweave_put((unsigned char*)output+8,5678,8);*received=short_reply?8:capacity;calls++;return 0;
}
int main(void){
 cudnnHandle_t h=(void*)1;cudnnRNNDescriptor_t r=(void*)2;cudnnRNNDataDescriptor_t d=(void*)3;size_t workspace=0,reserve=0;
 assert(cudnnGetRNNTempSpaceSizes(h,r,CUDNN_FWD_MODE_TRAINING,d,&workspace,NULL)==0&&workspace==1234);
 assert(cudnnGetRNNTempSpaceSizes(h,r,CUDNN_FWD_MODE_TRAINING,d,NULL,&reserve)==0&&reserve==5678);
 assert(cudnnGetRNNTempSpaceSizes(h,r,CUDNN_FWD_MODE_TRAINING,d,&workspace,&reserve)==0);
 assert(cudnnGetRNNTempSpaceSizes(h,r,CUDNN_FWD_MODE_TRAINING,d,NULL,NULL)==CUDNN_STATUS_BAD_PARAM&&calls==3);
 short_reply=1;workspace=99;assert(cudnnGetRNNTempSpaceSizes(h,r,CUDNN_FWD_MODE_TRAINING,d,&workspace,NULL)==CUDNN_STATUS_BAD_PARAM&&workspace==99);
 assert(cudnnCreateTensorDescriptor(NULL)==CUDNN_STATUS_BAD_PARAM&&calls==4);
 assert(cublasLtCreate(NULL)==CUBLAS_STATUS_INVALID_VALUE&&calls==4);
 puts("PASS: optional size outputs, null-output rejection, truncated response preserves caller storage");
}
