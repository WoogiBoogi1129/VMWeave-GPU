/* Real CPU cuDNN descriptors; mocked GPU handle, allocations, and execution.
 * Checks dispatch validation/marshalling, NOT GPU numerical correctness. */
#include "vmweave_library.h"
#include <cudnn.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>

static char input[1536],weight[432],output[2048],workspace[128];
static int forwards,workspace_queries,backend_status,forward_status;
static size_t required_workspace=64;
static void *current_stream;
cudnnStatus_t cudnnGetConvolutionForwardAlgorithmMaxCount(cudnnHandle_t h,int *n){assert(h==(void*)42);*n=8;return 0;}
cudnnStatus_t cudnnGetConvolutionForwardAlgorithm_v7(cudnnHandle_t h,const cudnnTensorDescriptor_t x,const cudnnFilterDescriptor_t w,const cudnnConvolutionDescriptor_t c,const cudnnTensorDescriptor_t y,int requested,int *n,cudnnConvolutionFwdAlgoPerf_t *perf){
    assert(h==(void*)42&&x&&w&&c&&y&&requested==8);*n=8;
    for(int i=0;i<8;i++)perf[i]=(cudnnConvolutionFwdAlgoPerf_t){.algo=i,.status=CUDNN_STATUS_SUCCESS,.time=.25f+i,.memory=UINT64_C(0x100000000)+i,.determinism=CUDNN_DETERMINISTIC,.mathType=CUDNN_FMA_MATH};
    return 0;
}
void *vmweave_compat_blas(uint64_t id){(void)id;return NULL;}
void *vmweave_compat_dnn(uint64_t id){return id==42?(void*)42:NULL;}
int vmweave_async_stream(uint64_t id,void **p){if(id!=0&&id!=43)return 0;*p=id?(void*)44:NULL;return 1;}
int vmweave_async_stream_id(void *p,uint64_t *id){if(p&&p!=(void*)44)return 0;*id=p?43:0;return 1;}
cudnnStatus_t cudnnSetStream(cudnnHandle_t h,cudaStream_t s){assert(h==(void*)42);current_stream=s;return 0;}
cudnnStatus_t cudnnGetStream(cudnnHandle_t h,cudaStream_t *s){assert(h==(void*)42);*s=current_stream;return 0;}
int vmweave_cuda_exec_resolve(struct vmweave_cuda_exec *e,struct vmweave_device_ref r,size_t bytes,void **p){
    (void)e;char *base=NULL;size_t capacity=0;
    switch(r.handle){case 10:base=input;capacity=sizeof(input);break;case 11:base=weight;capacity=sizeof(weight);break;case 12:base=output;capacity=sizeof(output);break;case 13:base=workspace;capacity=sizeof(workspace);break;}
    if(!base||r.offset>capacity||bytes>capacity-r.offset)return 0;
    *p=base+r.offset;return 1;
}
cudnnStatus_t cudnnGetConvolutionForwardWorkspaceSize(cudnnHandle_t h,const cudnnTensorDescriptor_t x,const cudnnFilterDescriptor_t w,const cudnnConvolutionDescriptor_t c,const cudnnTensorDescriptor_t y,cudnnConvolutionFwdAlgo_t a,size_t *bytes){
    assert(h==(void*)42&&x&&w&&c&&y&&a==CUDNN_CONVOLUTION_FWD_ALGO_IMPLICIT_GEMM);
    workspace_queries++;*bytes=required_workspace;return backend_status;
}
cudnnStatus_t cudnnConvolutionForward(cudnnHandle_t h,const void *alpha,const cudnnTensorDescriptor_t x,const void *xp,const cudnnFilterDescriptor_t w,const void *wp,const cudnnConvolutionDescriptor_t c,cudnnConvolutionFwdAlgo_t a,void *ws,size_t bytes,const void *beta,const cudnnTensorDescriptor_t y,void *yp){
    assert(h==(void*)42&&x&&w&&c&&y&&a==CUDNN_CONVOLUTION_FWD_ALGO_IMPLICIT_GEMM);
    assert(xp==input&&wp==weight&&yp==output&&ws==(required_workspace?workspace+8:NULL)&&bytes==required_workspace);
    assert(*(const float*)alpha==1.25f&&*(const float*)beta==.5f);forwards++;return forward_status;
}
static uint8_t p[VMWEAVE_LIBRARY_REQUEST],out[VMWEAVE_LIBRARY_RESPONSE];
static struct vmweave_shm_response response;
static int invoke(unsigned api){
    struct vmweave_cuda_session session={0};
    struct vmweave_shm_request q={.api_id=api,.payload_schema=1,.input=p,.input_bytes=sizeof(p)};
    memset(&response,0,sizeof(response));response.output=out;response.output_capacity=sizeof(out);
    vmweave_library_dispatch(&session,&q,&response);assert(!response.transport_status);return response.api_result;
}
#define SET(i,v) vmweave_put(p+8*(i),(uint64_t)(v),8)
#define GET(i) vmweave_get(out+8*(i),8)
#define CALL(name) invoke(VMWEAVE_LIB_##name)
static uint64_t tensor(int channels){
    assert(CALL(cudnnCreateTensorDescriptor)==0);uint64_t id=GET(0);
    memset(p,0,sizeof(p));SET(0,id);SET(1,CUDNN_DATA_FLOAT);SET(2,4);
    SET(3,2);SET(4,channels);SET(5,8);SET(6,8);SET(11,channels*64);SET(12,64);SET(13,8);SET(14,1);
    assert(CALL(cudnnSetTensorNdDescriptor)==0);return id;
}
int main(void){
    uint64_t x=tensor(3),y=tensor(4);
    assert(CALL(cudnnCreateFilterDescriptor)==0);uint64_t w=GET(0);
    memset(p,0,sizeof(p));SET(0,w);SET(1,CUDNN_DATA_FLOAT);SET(2,CUDNN_TENSOR_NCHW);SET(3,4);SET(4,4);SET(5,3);SET(6,3);SET(7,3);
    assert(CALL(cudnnSetFilterNdDescriptor)==0);
    SET(4,UINT64_MAX);assert(CALL(cudnnSetFilterNdDescriptor)==CUDNN_STATUS_BAD_PARAM);SET(4,4);
    SET(4,INT32_MAX);SET(5,INT32_MAX);SET(6,INT32_MAX);assert(CALL(cudnnSetFilterNdDescriptor)==CUDNN_STATUS_BAD_PARAM);
    SET(1,8);assert(CALL(cudnnGetFilterNdDescriptor)==0);assert(GET(2)==4&&GET(3)==4&&GET(4)==3&&GET(7)==0);
    SET(1,UINT64_C(0x100000004));assert(CALL(cudnnGetFilterNdDescriptor)==CUDNN_STATUS_BAD_PARAM);
    SET(1,CUDNN_DATA_HALF);assert(CALL(cudnnSetFilterNdDescriptor)==CUDNN_STATUS_NOT_SUPPORTED);
    SET(0,x);assert(CALL(cudnnDestroyFilterDescriptor)==CUDNN_STATUS_BAD_PARAM);
    assert(CALL(cudnnCreateConvolutionDescriptor)==0);uint64_t c=GET(0);
    memset(p,0,sizeof(p));SET(0,c);SET(1,2);SET(2,CUDNN_CROSS_CORRELATION);SET(3,CUDNN_DATA_FLOAT);
    SET(4,1);SET(5,1);SET(6,1);SET(7,1);SET(8,1);SET(9,1);assert(CALL(cudnnSetConvolutionNdDescriptor)==0);
    SET(4,UINT64_MAX);assert(CALL(cudnnSetConvolutionNdDescriptor)==CUDNN_STATUS_BAD_PARAM);SET(4,1);
    SET(8,2);assert(CALL(cudnnSetConvolutionNdDescriptor)==CUDNN_STATUS_NOT_SUPPORTED);SET(8,1);
    SET(1,6);assert(CALL(cudnnGetConvolutionNdDescriptor)==0);assert(GET(0)==2&&GET(3)==1&&GET(11)==1&&GET(19)==1&&GET(5)==0);
    SET(1,8);assert(CALL(cudnnGetConvolutionNdDescriptor)==CUDNN_STATUS_NOT_SUPPORTED);
    SET(1,2);assert(CALL(cudnnSetConvolutionGroupCount)==CUDNN_STATUS_NOT_SUPPORTED);
    SET(1,1);assert(CALL(cudnnSetConvolutionGroupCount)==0);
    assert(CALL(cudnnGetConvolutionGroupCount)==0&&GET(0)==1);
    SET(1,CUDNN_FMA_MATH);assert(CALL(cudnnSetConvolutionMathType)==0);
    assert(CALL(cudnnGetConvolutionMathType)==0&&GET(0)==CUDNN_FMA_MATH);
    SET(1,CUDNN_TENSOR_OP_MATH);assert(CALL(cudnnSetConvolutionMathType)==CUDNN_STATUS_NOT_SUPPORTED);
    SET(0,c);SET(1,x);SET(2,w);SET(3,4);assert(CALL(cudnnGetConvolutionNdForwardOutputDim)==0);
    assert(GET(0)==2&&GET(1)==4&&GET(2)==8&&GET(3)==8);
    for(int stream=0;stream<2;stream++){
        SET(0,42);SET(1,stream?43:0);assert(CALL(cudnnSetStream)==0);
        assert(CALL(cudnnGetStream)==0&&GET(0)==(stream?43:0));
        memset(p,0,sizeof(p));SET(0,42);SET(1,x);SET(2,w);SET(3,c);SET(4,y);
        assert(CALL(cudnnGetConvolutionForwardAlgorithmMaxCount)==0&&GET(0)==8);
        SET(5,8);assert(CALL(cudnnGetConvolutionForwardAlgorithm_v7)==0&&GET(0)==8);
        assert(GET(43)==7&&GET(46)==UINT64_C(0x100000007)&&GET(48)==CUDNN_FMA_MATH);
        float encoded_time;memcpy(&encoded_time,out+8*45,4);assert(encoded_time==7.25f);
        SET(5,9);assert(CALL(cudnnGetConvolutionForwardAlgorithm_v7)==CUDNN_STATUS_BAD_PARAM);
        SET(5,CUDNN_CONVOLUTION_FWD_ALGO_IMPLICIT_GEMM);SET(6,64);
        float alpha=1.25f,beta=.5f;memcpy(p+56,&alpha,4);memcpy(p+64,&beta,4);
        SET(9,10);SET(11,11);SET(13,12);SET(15,13);SET(16,8);
        assert(CALL(cudnnConvolutionForward)==0);assert(forwards==stream+1);
        int query_count=workspace_queries;
        SET(1,w);assert(CALL(cudnnConvolutionForward)==CUDNN_STATUS_BAD_PARAM);assert(workspace_queries==query_count);SET(1,x);
        SET(4,x);assert(CALL(cudnnConvolutionForward)==CUDNN_STATUS_NOT_SUPPORTED);SET(4,y);
        SET(6,63);assert(CALL(cudnnConvolutionForward)==CUDNN_STATUS_BAD_PARAM);SET(6,64);
        for(int ref=9;ref<=15;ref+=2){
            uint64_t old=vmweave_get(p+8*ref,8),offset=vmweave_get(p+8*(ref+1),8);
            SET(ref,999);assert(CALL(cudnnConvolutionForward)==CUDNN_STATUS_BAD_PARAM);
            SET(ref,0);assert(CALL(cudnnConvolutionForward)==CUDNN_STATUS_BAD_PARAM);SET(ref,old);
            SET(ref+1,UINT64_MAX);assert(CALL(cudnnConvolutionForward)==CUDNN_STATUS_BAD_PARAM);
            SET(ref+1,ref==15?65:1);assert(CALL(cudnnConvolutionForward)==CUDNN_STATUS_BAD_PARAM);SET(ref+1,offset);
        }
        backend_status=CUDNN_STATUS_NOT_SUPPORTED;assert(CALL(cudnnConvolutionForward)==backend_status);backend_status=0;
        assert(forwards==stream+1);
    }
    required_workspace=0;SET(6,0);SET(15,0);SET(16,0);
    assert(CALL(cudnnConvolutionForward)==0&&forwards==3);
    SET(16,1);assert(CALL(cudnnConvolutionForward)==CUDNN_STATUS_BAD_PARAM&&forwards==3);SET(16,0);
    forward_status=CUDNN_STATUS_EXECUTION_FAILED;
    assert(CALL(cudnnConvolutionForward)==CUDNN_STATUS_EXECUTION_FAILED&&forwards==4);
    SET(0,c);assert(CALL(cudnnDestroyConvolutionDescriptor)==0);
    assert(CALL(cudnnDestroyConvolutionDescriptor)==CUDNN_STATUS_BAD_PARAM);
    assert(vmweave_library_close()==0);SET(0,w);assert(CALL(cudnnDestroyFilterDescriptor)==CUDNN_STATUS_BAD_PARAM);
    assert(CALL(cudnnCreateFilterDescriptor)==0);assert(GET(0)!=w);assert(vmweave_library_close()==0);
    for(int i=0;i<4096;i++)assert(CALL(cudnnCreateFilterDescriptor)==0);
    assert(CALL(cudnnCreateFilterDescriptor)==CUDNN_STATUS_ALLOC_FAILED);
    assert(vmweave_library_close()==0);
    assert(CALL(cudnnCreateConvolutionDescriptor)==0);assert(vmweave_library_close()==0);
    puts("PASS: real convolution descriptors, type/lifetime/overflow, stream translation, allocation offsets, workspace bounds, backend error propagation (execution mocked)");
}
