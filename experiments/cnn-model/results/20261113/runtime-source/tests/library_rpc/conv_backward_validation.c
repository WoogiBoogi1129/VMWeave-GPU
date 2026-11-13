/* Real CPU descriptors, mock execution: verify both backward roles and bounds. */
#define main forward_validation_main
#include "conv_validation.c"
#undef main
static int data_calls,filter_calls,query_status,exec_status,perf_count=6;
static void check_roles(cudnnHandle_t h,void *x,void *w,void *c,void *y){
    assert(h==(void*)42&&x&&w&&c&&y);
    int n,d[4],s[4];cudnnDataType_t type;cudnnTensorFormat_t format;
    assert(cudnnGetTensorNdDescriptor(x,4,&type,&n,d,s)==0&&d[1]==3);
    assert(cudnnGetTensorNdDescriptor(y,4,&type,&n,d,s)==0&&d[1]==4);
    assert(cudnnGetFilterNdDescriptor(w,4,&type,&format,&n,d)==0&&d[0]==4&&d[1]==3);
}
cudnnStatus_t cudnnGetConvolutionBackwardDataAlgorithmMaxCount(cudnnHandle_t h,int *n){assert(h==(void*)42);*n=6;return 0;}
cudnnStatus_t cudnnGetConvolutionBackwardFilterAlgorithmMaxCount(cudnnHandle_t h,int *n){assert(h==(void*)42);*n=7;return 0;}
#define PERF_BODY check_roles(h,x,w,c,y);assert(requested==6);*n=perf_count;for(int i=0;i<6;i++){perf[i].algo=i;perf[i].status=CUDNN_STATUS_SUCCESS;perf[i].time=.5f+i;perf[i].memory=UINT64_C(0x100000000)+i;perf[i].determinism=CUDNN_DETERMINISTIC;perf[i].mathType=CUDNN_FMA_MATH;}return 0
cudnnStatus_t cudnnGetConvolutionBackwardDataAlgorithm_v7(cudnnHandle_t h,const cudnnFilterDescriptor_t w,const cudnnTensorDescriptor_t y,const cudnnConvolutionDescriptor_t c,const cudnnTensorDescriptor_t x,int requested,int *n,cudnnConvolutionBwdDataAlgoPerf_t *perf){PERF_BODY;}
cudnnStatus_t cudnnGetConvolutionBackwardFilterAlgorithm_v7(cudnnHandle_t h,const cudnnTensorDescriptor_t x,const cudnnTensorDescriptor_t y,const cudnnConvolutionDescriptor_t c,const cudnnFilterDescriptor_t w,int requested,int *n,cudnnConvolutionBwdFilterAlgoPerf_t *perf){PERF_BODY;}
cudnnStatus_t cudnnGetConvolutionBackwardDataWorkspaceSize(cudnnHandle_t h,const cudnnFilterDescriptor_t w,const cudnnTensorDescriptor_t y,const cudnnConvolutionDescriptor_t c,const cudnnTensorDescriptor_t x,cudnnConvolutionBwdDataAlgo_t a,size_t *bytes){check_roles(h,x,w,c,y);assert(a==1);*bytes=required_workspace;return query_status;}
cudnnStatus_t cudnnGetConvolutionBackwardFilterWorkspaceSize(cudnnHandle_t h,const cudnnTensorDescriptor_t x,const cudnnTensorDescriptor_t y,const cudnnConvolutionDescriptor_t c,const cudnnFilterDescriptor_t w,cudnnConvolutionBwdFilterAlgo_t a,size_t *bytes){check_roles(h,x,w,c,y);assert(a==1);*bytes=required_workspace;return query_status;}
#define EXEC_CHECK check_roles(h,x,w,c,y);assert(a==1&&xp==input&&wp==weight&&yp==output);assert(ws==(required_workspace?workspace+8:NULL)&&bytes==required_workspace);assert(*(const float*)alpha==1.25f&&*(const float*)beta==.5f)
cudnnStatus_t cudnnConvolutionBackwardData(cudnnHandle_t h,const void *alpha,const cudnnFilterDescriptor_t w,const void *wp,const cudnnTensorDescriptor_t y,const void *yp,const cudnnConvolutionDescriptor_t c,cudnnConvolutionBwdDataAlgo_t a,void *ws,size_t bytes,const void *beta,const cudnnTensorDescriptor_t x,void *xp){EXEC_CHECK;data_calls++;return exec_status;}
cudnnStatus_t cudnnConvolutionBackwardFilter(cudnnHandle_t h,const void *alpha,const cudnnTensorDescriptor_t x,const void *xp,const cudnnTensorDescriptor_t y,const void *yp,const cudnnConvolutionDescriptor_t c,cudnnConvolutionBwdFilterAlgo_t a,void *ws,size_t bytes,const void *beta,const cudnnFilterDescriptor_t w,void *wp){EXEC_CHECK;filter_calls++;return exec_status;}
int main(void){
    uint64_t x=tensor(3),y=tensor(4);
    assert(CALL(cudnnCreateFilterDescriptor)==0);uint64_t w=GET(0);
    SET(0,w);SET(1,CUDNN_DATA_FLOAT);SET(2,CUDNN_TENSOR_NCHW);SET(3,4);SET(4,4);SET(5,3);SET(6,3);SET(7,3);assert(CALL(cudnnSetFilterNdDescriptor)==0);
    assert(CALL(cudnnCreateConvolutionDescriptor)==0);uint64_t c=GET(0);
    SET(0,c);SET(1,2);SET(2,CUDNN_CROSS_CORRELATION);SET(3,CUDNN_DATA_FLOAT);
    for(int i=4;i<10;i++)SET(i,1);
    assert(CALL(cudnnSetConvolutionNdDescriptor)==0);
    unsigned execution[]={VMWEAVE_LIB_cudnnConvolutionBackwardData,VMWEAVE_LIB_cudnnConvolutionBackwardFilter};
    unsigned heuristic[]={VMWEAVE_LIB_cudnnGetConvolutionBackwardDataAlgorithm_v7,VMWEAVE_LIB_cudnnGetConvolutionBackwardFilterAlgorithm_v7};
    unsigned maxcount[]={VMWEAVE_LIB_cudnnGetConvolutionBackwardDataAlgorithmMaxCount,VMWEAVE_LIB_cudnnGetConvolutionBackwardFilterAlgorithmMaxCount};
    for(int dir=0;dir<2;dir++)for(int stream=0;stream<2;stream++){
        SET(0,42);SET(1,stream?43:0);assert(CALL(cudnnSetStream)==0);
        assert(CALL(cudnnGetStream)==0&&GET(0)==(stream?43:0));
        memset(p,0,sizeof(p));SET(0,42);SET(1,x);SET(2,w);SET(3,c);SET(4,y);
        assert(invoke(maxcount[dir])==0&&GET(0)==6+dir);
        SET(5,6);assert(invoke(heuristic[dir])==0&&GET(0)==6&&GET(34)==UINT64_C(0x100000005));
        perf_count=7;assert(invoke(heuristic[dir])==CUDNN_STATUS_BAD_PARAM);perf_count=6;
        SET(5,UINT64_C(0x100000006));assert(invoke(heuristic[dir])==CUDNN_STATUS_BAD_PARAM);
        SET(5,1);SET(6,64);required_workspace=64;float alpha=1.25f,beta=.5f;
        memcpy(p+56,&alpha,4);memcpy(p+64,&beta,4);SET(9,10);SET(11,11);SET(13,12);SET(15,13);SET(16,8);
        int before=data_calls+filter_calls;assert(invoke(execution[dir])==0&&data_calls+filter_calls==before+1);
        for(int ref=9;ref<=15;ref+=2){
            uint64_t old=vmweave_get(p+8*ref,8),offset=vmweave_get(p+8*(ref+1),8);
            SET(ref,999);assert(invoke(execution[dir])==CUDNN_STATUS_BAD_PARAM);
            SET(ref,0);assert(invoke(execution[dir])==CUDNN_STATUS_BAD_PARAM);SET(ref,old);
            SET(ref+1,UINT64_MAX);assert(invoke(execution[dir])==CUDNN_STATUS_BAD_PARAM);
            SET(ref+1,ref==15?65:1);assert(invoke(execution[dir])==CUDNN_STATUS_BAD_PARAM);SET(ref+1,offset);
        }
        SET(6,63);assert(invoke(execution[dir])==CUDNN_STATUS_BAD_PARAM);SET(6,64);
        SET(1,w);assert(invoke(execution[dir])==CUDNN_STATUS_BAD_PARAM);SET(1,x);
        SET(4,x);assert(invoke(execution[dir])==CUDNN_STATUS_NOT_SUPPORTED);SET(4,y);
        SET(5,UINT64_MAX);assert(invoke(execution[dir])==CUDNN_STATUS_BAD_PARAM);SET(5,1);
        query_status=CUDNN_STATUS_NOT_SUPPORTED;assert(invoke(execution[dir])==query_status);query_status=0;
        assert(data_calls+filter_calls==before+1);
        required_workspace=0;SET(6,0);SET(15,0);SET(16,0);assert(invoke(execution[dir])==0);
        SET(16,1);assert(invoke(execution[dir])==CUDNN_STATUS_BAD_PARAM);SET(16,0);
        exec_status=CUDNN_STATUS_EXECUTION_FAILED;assert(invoke(execution[dir])==exec_status);exec_status=0;
        assert(data_calls+filter_calls==before+3);
    }
    SET(0,w);assert(CALL(cudnnDestroyFilterDescriptor)==0);SET(0,42);
    assert(CALL(cudnnConvolutionBackwardData)==CUDNN_STATUS_BAD_PARAM);
    assert(CALL(cudnnConvolutionBackwardFilter)==CUDNN_STATUS_BAD_PARAM);
    assert(vmweave_library_close()==0);
    puts("PASS: backward data/filter roles, streams, bounds, workspace/null/overflow, descriptor type/shape/lifetime, heuristic count and native errors (GPU execution mocked)");
}
