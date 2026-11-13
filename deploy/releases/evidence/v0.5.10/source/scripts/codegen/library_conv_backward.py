"""Legacy FP32 Conv2d gradients. Canonical slots retain forward tensor roles:
0=handle, 1=x/dx descriptor, 2=w/dw descriptor, 3=conv, 4=y/dy descriptor.
Pointer slots 9/11/13 carry x/dx, w/dw, and dy respectively. No native structs.
"""
IDS.update({
    'cudnnGetConvolutionBackwardDataAlgorithmMaxCount': 0x3334,
    'cudnnGetConvolutionBackwardDataAlgorithm_v7': 0x3335,
    'cudnnGetConvolutionBackwardDataWorkspaceSize': 0x3336,
    'cudnnConvolutionBackwardData': 0x3337,
    'cudnnGetConvolutionBackwardFilterAlgorithmMaxCount': 0x3338,
    'cudnnGetConvolutionBackwardFilterAlgorithm_v7': 0x3339,
    'cudnnGetConvolutionBackwardFilterWorkspaceSize': 0x333a,
    'cudnnConvolutionBackwardFilter': 0x333b,
})

for direction, enum, args, native in [
    ('Data', 'DATA',
     'cudnnHandle_t handle,cudnnFilterDescriptor_t wd,cudnnTensorDescriptor_t yd,cudnnConvolutionDescriptor_t cd,cudnnTensorDescriptor_t xd',
     'h,w,y,c,x'),
    ('Filter', 'FILTER',
     'cudnnHandle_t handle,cudnnTensorDescriptor_t xd,cudnnTensorDescriptor_t yd,cudnnConvolutionDescriptor_t cd,cudnnFilterDescriptor_t wd',
     'h,x,y,c,w'),
]:
    prefix='cudnnGetConvolutionBackward'+direction
    algo='cudnnConvolutionBwd'+direction+'Algo_t'
    perf='cudnnConvolutionBwd'+direction+'AlgoPerf_t'
    count='CUDNN_CONVOLUTION_BWD_'+enum+'_ALGO_COUNT'
    add(prefix+'AlgorithmMaxCount',D,'cudnnHandle_t handle,int *count',
        'if(!count) BAD;PUT(0,handle);AFTER(*count=GET(0));',
        f'DNN(0,h);int count;rc={prefix}AlgorithmMaxCount(h,&count);if(!rc){{if(count<1||count>8) UNSUP;OUT(0,count);}}')
    add(prefix+'Algorithm_v7',D,args+f',int requested,int *returned,{perf} perf[]',
        'if(requested<1||requested>8||!returned||!perf) BAD;'+tuple_guest+
        'PUT(5,requested);AFTER(if(GET(0)>(uint64_t)requested) BAD;*returned=GET(0);for(int i=0;i<*returned;i++){memset(&perf[i],0,sizeof(perf[i]));perf[i].algo=GET(1+6*i);perf[i].status=GET(2+6*i);memcpy(&perf[i].time,out+8*(3+6*i),4);perf[i].memory=GET(4+6*i);perf[i].determinism=GET(5+6*i);perf[i].mathType=GET(6+6*i);});',
        tuple_worker+f'if(A(5)<1||A(5)>8) BAD;int n=0;{perf} perf[8]={{0}};rc={prefix}Algorithm_v7({native},A(5),&n,perf);'+
        'if(!rc){if(n<0||n>A(5)) BAD;OUT(0,n);for(int i=0;i<n;i++){OUT(1+6*i,perf[i].algo);OUT(2+6*i,perf[i].status);memcpy(out+8*(3+6*i),&perf[i].time,4);OUT(4+6*i,perf[i].memory);OUT(5+6*i,perf[i].determinism);OUT(6+6*i,perf[i].mathType);}}')
    add(prefix+'WorkspaceSize',D,args+f',{algo} algo,size_t *bytes',
        'if(!bytes) BAD;'+tuple_guest+'PUT(5,algo);AFTER(*bytes=GET(0));',
        tuple_worker+f'if(A(5)>={count}) BAD;size_t bytes;rc={prefix}WorkspaceSize({native},A(5),&bytes);if(!rc)OUT(0,bytes);')
    if direction=='Data':
        args='cudnnHandle_t handle,const void *alpha,cudnnFilterDescriptor_t wd,const void *weights,cudnnTensorDescriptor_t yd,const void *dy,cudnnConvolutionDescriptor_t cd,cudnnConvolutionBwdDataAlgo_t algo,void *workspace,size_t bytes,const void *beta,cudnnTensorDescriptor_t xd,void *dx'
        refs='REF(9,dx,0);REF(11,weights,0);REF(13,dy,0);'
        resolve='DEV(9,tensor_bytes(x),0,dx);DEV(11,filter_bytes(w),0,weights);DEV(13,tensor_bytes(y),0,dy);'
        execute='cudnnConvolutionBackwardData(h,&alpha,w,weights,y,dy,c,A(5),workspace,A(6),&beta,x,dx)'
    else:
        args='cudnnHandle_t handle,const void *alpha,cudnnTensorDescriptor_t xd,const void *input,cudnnTensorDescriptor_t yd,const void *dy,cudnnConvolutionDescriptor_t cd,cudnnConvolutionBwdFilterAlgo_t algo,void *workspace,size_t bytes,const void *beta,cudnnFilterDescriptor_t wd,void *dw'
        refs='REF(9,input,0);REF(11,dw,0);REF(13,dy,0);'
        resolve='DEV(9,tensor_bytes(x),0,input);DEV(11,filter_bytes(w),0,dw);DEV(13,tensor_bytes(y),0,dy);'
        execute='cudnnConvolutionBackwardFilter(h,&alpha,x,input,y,dy,c,A(5),workspace,A(6),&beta,w,dw)'
    add('cudnnConvolutionBackward'+direction,D,args,
        'if(!alpha||!beta) BAD;'+tuple_guest+'PUT(5,algo);PUT(6,bytes);memcpy(p+56,alpha,4);memcpy(p+64,beta,4);'+refs+'REF(15,workspace,bytes);',
        tuple_worker+f'if(A(5)>={count}) BAD;size_t required=0;rc={prefix}WorkspaceSize({native},A(5),&required);if(rc)break;if(A(6)<required) BAD;'+resolve+
        'DEV(15,A(6),A(6)==0,workspace);float alpha,beta;memcpy(&alpha,p+56,4);memcpy(&beta,p+64,4);rc='+execute+';')
