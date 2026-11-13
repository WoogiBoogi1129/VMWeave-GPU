/* Guest field encoding and bounded output decoding; no transport/GPU. */
#include "vmweave_guest.h"
#include "vmweave_library.h"
#include <cudnn.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
pthread_mutex_t vmweave_guest_lock=PTHREAD_MUTEX_INITIALIZER;
static int calls,short_reply,oversize_count;
static char input[1536],weight[432],output[2048],workspace[128];
int vmweave_guest_ref(const void *p,size_t bytes,struct vmweave_device_ref *r){
    if(p==input)*r=(struct vmweave_device_ref){10,0};
    else if(p==weight)*r=(struct vmweave_device_ref){11,0};
    else if(p==output)*r=(struct vmweave_device_ref){12,0};
    else if(p==workspace+8&&bytes<=120)*r=(struct vmweave_device_ref){13,8};
    else return -1;
    return 0;
}
int vmweave_guest_exchange(uint32_t api,const void *input_bytes,size_t bytes,void *output_bytes,size_t cap,size_t *got){
    assert(bytes==VMWEAVE_LIBRARY_REQUEST&&cap==VMWEAVE_LIBRARY_RESPONSE);
    const uint8_t *p=input_bytes;uint8_t *out=output_bytes;memset(out,0,cap);*got=short_reply?8:cap;calls++;
    for(int i=0;i<5;i++)assert(vmweave_get(p+8*i,8)==42+i);
    if(api==VMWEAVE_LIB_cudnnConvolutionForward){
        assert(vmweave_get(p+48,8)==64);
        float alpha,beta;memcpy(&alpha,p+56,4);memcpy(&beta,p+64,4);assert(alpha==1.25f&&beta==.5f);
        assert(vmweave_get(p+72,8)==10&&vmweave_get(p+88,8)==11&&vmweave_get(p+104,8)==12&&vmweave_get(p+120,8)==13&&vmweave_get(p+128,8)==8);
    }else{
        assert(api==VMWEAVE_LIB_cudnnGetConvolutionForwardAlgorithm_v7&&vmweave_get(p+40,8)==8);
        vmweave_put(out,oversize_count?9:8,8);
        for(int i=0;i<8;i++){
            vmweave_put(out+8*(1+6*i),i,8);vmweave_put(out+8*(2+6*i),CUDNN_STATUS_SUCCESS,8);
            float t=.25f+i;memcpy(out+8*(3+6*i),&t,4);vmweave_put(out+8*(4+6*i),UINT64_C(0x100000000)+i,8);
            vmweave_put(out+8*(5+6*i),CUDNN_DETERMINISTIC,8);vmweave_put(out+8*(6+6*i),CUDNN_FMA_MATH,8);
        }
    }
    return 0;
}
int main(void){
    cudnnHandle_t h=(void*)42;cudnnTensorDescriptor_t x=(void*)43,y=(void*)46;
    cudnnFilterDescriptor_t w=(void*)44;cudnnConvolutionDescriptor_t c=(void*)45;
    float alpha=1.25f,beta=.5f;
    assert(cudnnConvolutionForward(h,&alpha,x,input,w,weight,c,0,workspace+8,64,&beta,y,output)==0);
    assert(cudnnConvolutionForward(h,&alpha,x,input+1,w,weight,c,0,workspace+8,64,&beta,y,output)==CUDNN_STATUS_BAD_PARAM);
    assert(cudnnConvolutionForward(h,&alpha,x,input,w,weight,c,0,NULL,64,&beta,y,output)==CUDNN_STATUS_BAD_PARAM);
    assert(cudnnConvolutionForward(h,NULL,x,input,w,weight,c,0,workspace+8,64,&beta,y,output)==CUDNN_STATUS_BAD_PARAM&&calls==1);
    struct {cudnnConvolutionFwdAlgoPerf_t perf[8];uint64_t sentinel;} result={.sentinel=1234};int n=-1;
    assert(cudnnGetConvolutionForwardAlgorithm_v7(h,x,w,c,y,8,&n,result.perf)==0&&n==8);
    assert(result.perf[7].algo==7&&result.perf[7].time==7.25f&&result.perf[7].memory==UINT64_C(0x100000007)&&result.perf[7].mathType==CUDNN_FMA_MATH&&result.sentinel==1234);
    unsigned char snapshot[sizeof(result)];memcpy(snapshot,&result,sizeof(result));n=-1;oversize_count=1;
    assert(cudnnGetConvolutionForwardAlgorithm_v7(h,x,w,c,y,8,&n,result.perf)==CUDNN_STATUS_BAD_PARAM&&n==-1&&!memcmp(snapshot,&result,sizeof(result)));
    oversize_count=0;short_reply=1;
    assert(cudnnGetConvolutionForwardAlgorithm_v7(h,x,w,c,y,8,&n,result.perf)==CUDNN_STATUS_BAD_PARAM&&n==-1&&!memcmp(snapshot,&result,sizeof(result)));
    assert(cudnnGetConvolutionForwardAlgorithm_v7(h,x,w,c,y,9,&n,result.perf)==CUDNN_STATUS_BAD_PARAM&&calls==4);
    assert(cudnnCreateFilterDescriptor(NULL)==CUDNN_STATUS_BAD_PARAM);
    assert(cudnnCreateConvolutionDescriptor(NULL)==CUDNN_STATUS_BAD_PARAM);
    int dims[4]={4,3,3,3},pad[2]={1,1},stride[2]={1,1},dilation[2]={1,1};
    assert(cudnnSetFilterNdDescriptor(w,CUDNN_DATA_HALF,CUDNN_TENSOR_NCHW,4,dims)==CUDNN_STATUS_NOT_SUPPORTED);
    dims[0]=-1;assert(cudnnSetFilterNdDescriptor(w,CUDNN_DATA_FLOAT,CUDNN_TENSOR_NCHW,4,dims)==CUDNN_STATUS_BAD_PARAM);
    assert(cudnnSetConvolutionNdDescriptor(c,2,NULL,stride,dilation,CUDNN_CROSS_CORRELATION,CUDNN_DATA_FLOAT)==CUDNN_STATUS_BAD_PARAM);
    dilation[0]=2;assert(cudnnSetConvolutionNdDescriptor(c,2,pad,stride,dilation,CUDNN_CROSS_CORRELATION,CUDNN_DATA_FLOAT)==CUDNN_STATUS_NOT_SUPPORTED);
    assert(calls==4);
    puts("PASS: convolution Guest scalar/ref encoding, 64-bit heuristic decode, invalid pointers, malformed reply count/length and caller storage preservation");
}
