"""Bounded legacy cuDNN forward RPC. Executed by library_rpc.py.

FP32 contiguous NCHW, 2D cross-correlation, groups=1, dilation=1.
IDs are append-only. No native structs or host pointers cross the wire.
"""
IDS.update({
    'cudnnCreateFilterDescriptor': 0x3323,
    'cudnnDestroyFilterDescriptor': 0x3324,
    'cudnnCreateConvolutionDescriptor': 0x3325,
    'cudnnDestroyConvolutionDescriptor': 0x3326,
    'cudnnSetFilterNdDescriptor': 0x3327,
    'cudnnGetFilterNdDescriptor': 0x3328,
    'cudnnSetConvolutionNdDescriptor': 0x3329,
    'cudnnGetConvolutionNdDescriptor': 0x332a,
    'cudnnSetConvolutionGroupCount': 0x332b,
    'cudnnGetConvolutionGroupCount': 0x332c,
    'cudnnSetConvolutionMathType': 0x332d,
    'cudnnGetConvolutionMathType': 0x332e,
    'cudnnGetConvolutionNdForwardOutputDim': 0x332f,
    'cudnnGetConvolutionForwardAlgorithmMaxCount': 0x3330,
    'cudnnGetConvolutionForwardAlgorithm_v7': 0x3331,
    'cudnnGetConvolutionForwardWorkspaceSize': 0x3332,
    'cudnnConvolutionForward': 0x3333,
})
for name,typ,kind in [('Filter','cudnnFilterDescriptor_t','FILTER'),('Convolution','cudnnConvolutionDescriptor_t','CONV')]:
    add('cudnnCreate'+name+'Descriptor',D,f'{typ} *desc',
        f'if(!desc) BAD;AFTER(*desc=({typ})(uintptr_t)GET(0));',
        f'void *v=NULL; rc=cudnnCreate{name}Descriptor(({typ}*)&v); if(!rc) rc=save_object({kind},v,out);')
    add('cudnnDestroy'+name+'Descriptor',D,f'{typ} desc','PUT(0,desc);',
        f'OBJ(0,{kind},d); rc=cudnnDestroy{name}Descriptor(d); if(!rc) drop_object(A(0));')

add('cudnnSetFilterNdDescriptor',D,
    'cudnnFilterDescriptor_t desc,cudnnDataType_t type,cudnnTensorFormat_t format,int n,const int dims[]',
    'if(!dims) BAD; if(type!=CUDNN_DATA_FLOAT||format!=CUDNN_TENSOR_NCHW||n!=4) UNSUP; PUT(0,desc);PUT(1,type);PUT(2,format);PUT(3,n);for(int i=0;i<4;i++){if(dims[i]<1) BAD;PUT(4+i,dims[i]);}',
    'OBJ(0,FILTER,d);if(A(1)!=CUDNN_DATA_FLOAT||A(2)!=CUDNN_TENSOR_NCHW||A(3)!=4) UNSUP;int dims[4];size_t bytes=4;for(int i=0;i<4;i++){if(!A(4+i)||A(4+i)>INT32_MAX||A(4+i)>SIZE_MAX/bytes) BAD;dims[i]=A(4+i);bytes*=dims[i];}rc=cudnnSetFilterNdDescriptor(d,A(1),A(2),4,dims);')
add('cudnnGetFilterNdDescriptor',D,
    'cudnnFilterDescriptor_t desc,int requested,cudnnDataType_t *type,cudnnTensorFormat_t *format,int *n,int dims[]',
    'if(requested<4||requested>8||!type||!format||!n||!dims) BAD;PUT(0,desc);PUT(1,requested);AFTER(*type=GET(0);*format=GET(1);*n=GET(2);for(int i=0;i<requested;i++)dims[i]=GET(3+i));',
    'OBJ(0,FILTER,d);if(A(1)<4||A(1)>8) BAD;int n=0,dims[8]={0};cudnnDataType_t type;cudnnTensorFormat_t format;rc=cudnnGetFilterNdDescriptor(d,A(1),&type,&format,&n,dims);if(!rc){OUT(0,type);OUT(1,format);OUT(2,n);for(int i=0;i<A(1);i++)OUT(3+i,dims[i]);}')
add('cudnnSetConvolutionNdDescriptor',D,
    'cudnnConvolutionDescriptor_t desc,int n,const int pad[],const int stride[],const int dilation[],cudnnConvolutionMode_t mode,cudnnDataType_t type',
    'if(!pad||!stride||!dilation) BAD;if(n!=2||mode!=CUDNN_CROSS_CORRELATION||type!=CUDNN_DATA_FLOAT) UNSUP;PUT(0,desc);PUT(1,n);PUT(2,mode);PUT(3,type);for(int i=0;i<2;i++){if(pad[i]<0||stride[i]<1) BAD;if(dilation[i]!=1) UNSUP;PUT(4+i,pad[i]);PUT(6+i,stride[i]);PUT(8+i,dilation[i]);}',
    'OBJ(0,CONV,d);if(A(1)!=2||A(2)!=CUDNN_CROSS_CORRELATION||A(3)!=CUDNN_DATA_FLOAT) UNSUP;int pad[2],stride[2],dilation[2];for(int i=0;i<2;i++){if(A(4+i)>INT32_MAX||!A(6+i)||A(6+i)>INT32_MAX) BAD;if(A(8+i)!=1) UNSUP;pad[i]=A(4+i);stride[i]=A(6+i);dilation[i]=1;}rc=cudnnSetConvolutionNdDescriptor(d,2,pad,stride,dilation,A(2),A(3));')
add('cudnnGetConvolutionNdDescriptor',D,
    'cudnnConvolutionDescriptor_t desc,int requested,int *n,int pad[],int stride[],int dilation[],cudnnConvolutionMode_t *mode,cudnnDataType_t *type',
    'if(requested<2||requested>8||!n||!pad||!stride||!dilation||!mode||!type) BAD;PUT(0,desc);PUT(1,requested);AFTER(*n=GET(0);*mode=GET(1);*type=GET(2);for(int i=0;i<requested;i++){pad[i]=GET(3+i);stride[i]=GET(11+i);dilation[i]=GET(19+i);});',
    'OBJ(0,CONV,d);if(A(1)<2||A(1)>8) BAD;int n=0,pad[8]={0},stride[8]={0},dilation[8]={0};cudnnConvolutionMode_t mode;cudnnDataType_t type;rc=cudnnGetConvolutionNdDescriptor(d,A(1),&n,pad,stride,dilation,&mode,&type);if(!rc){OUT(0,n);OUT(1,mode);OUT(2,type);for(int i=0;i<A(1);i++){OUT(3+i,pad[i]);OUT(11+i,stride[i]);OUT(19+i,dilation[i]);}}')
for suffix,typ,valid in [('GroupCount','int','value==1'),('MathType','cudnnMathType_t','value==CUDNN_DEFAULT_MATH||value==CUDNN_FMA_MATH')]:
    add('cudnnSetConvolution'+suffix,D,f'cudnnConvolutionDescriptor_t desc,{typ} value',
        f'if(!({valid})) UNSUP;PUT(0,desc);PUT(1,value);',
        f'OBJ(0,CONV,d);uint64_t value=A(1);if(!({valid})) UNSUP;rc=cudnnSetConvolution{suffix}(d,value);')
    add('cudnnGetConvolution'+suffix,D,f'cudnnConvolutionDescriptor_t desc,{typ} *value',
        'if(!value) BAD;PUT(0,desc);AFTER(*value=GET(0));',
        f'OBJ(0,CONV,d);{typ} value;rc=cudnnGetConvolution{suffix}(d,&value);if(!rc)OUT(0,value);')
add('cudnnGetConvolutionNdForwardOutputDim',D,
    'cudnnConvolutionDescriptor_t conv,cudnnTensorDescriptor_t x,cudnnFilterDescriptor_t w,int n,int dims[]',
    'if(n!=4||!dims) BAD;PUT(0,conv);PUT(1,x);PUT(2,w);PUT(3,n);AFTER(for(int i=0;i<4;i++)dims[i]=GET(i));',
    'OBJ(0,CONV,c);OBJ(1,TENSOR,x);OBJ(2,FILTER,w);if(A(3)!=4) BAD;int dims[4];if(!conv_input_valid(x,w,c)) UNSUP;rc=cudnnGetConvolutionNdForwardOutputDim(c,x,w,4,dims);if(!rc)for(int i=0;i<4;i++)OUT(i,dims[i]);')
add('cudnnGetConvolutionForwardAlgorithmMaxCount',D,'cudnnHandle_t handle,int *count',
    'if(!count) BAD;PUT(0,handle);AFTER(*count=GET(0));',
    'DNN(0,h);int count;rc=cudnnGetConvolutionForwardAlgorithmMaxCount(h,&count);if(!rc){if(count<1||count>8) UNSUP;OUT(0,count);}')

# Slots 0..4 are the same descriptor tuple for heuristic/workspace/forward.
tuple_args='cudnnHandle_t handle,cudnnTensorDescriptor_t xd,cudnnFilterDescriptor_t wd,cudnnConvolutionDescriptor_t cd,cudnnTensorDescriptor_t yd'
tuple_guest='PUT(0,handle);PUT(1,xd);PUT(2,wd);PUT(3,cd);PUT(4,yd);'
tuple_worker='DNN(0,h);OBJ(1,TENSOR,x);OBJ(2,FILTER,w);OBJ(3,CONV,c);OBJ(4,TENSOR,y);if(!conv_valid(x,w,c,y)) UNSUP;'
add('cudnnGetConvolutionForwardAlgorithm_v7',D,
    tuple_args+',int requested,int *returned,cudnnConvolutionFwdAlgoPerf_t perf[]',
    'if(requested<1||requested>8||!returned||!perf) BAD;'+tuple_guest+'PUT(5,requested);AFTER(if(GET(0)>(uint64_t)requested) BAD;*returned=GET(0);for(int i=0;i<*returned;i++){memset(&perf[i],0,sizeof(perf[i]));perf[i].algo=GET(1+6*i);perf[i].status=GET(2+6*i);memcpy(&perf[i].time,out+8*(3+6*i),4);perf[i].memory=GET(4+6*i);perf[i].determinism=GET(5+6*i);perf[i].mathType=GET(6+6*i);});',
    tuple_worker+'if(A(5)<1||A(5)>8) BAD;int n=0;cudnnConvolutionFwdAlgoPerf_t perf[8]={0};rc=cudnnGetConvolutionForwardAlgorithm_v7(h,x,w,c,y,A(5),&n,perf);if(!rc){if(n<0||n>A(5)) BAD;OUT(0,n);for(int i=0;i<n;i++){OUT(1+6*i,perf[i].algo);OUT(2+6*i,perf[i].status);memcpy(out+8*(3+6*i),&perf[i].time,4);OUT(4+6*i,perf[i].memory);OUT(5+6*i,perf[i].determinism);OUT(6+6*i,perf[i].mathType);}}')
add('cudnnGetConvolutionForwardWorkspaceSize',D,
    tuple_args+',cudnnConvolutionFwdAlgo_t algo,size_t *bytes',
    'if(!bytes) BAD;'+tuple_guest+'PUT(5,algo);AFTER(*bytes=GET(0));',
    tuple_worker+'if(A(5)>=CUDNN_CONVOLUTION_FWD_ALGO_COUNT) BAD;size_t bytes;rc=cudnnGetConvolutionForwardWorkspaceSize(h,x,w,c,y,A(5),&bytes);if(!rc)OUT(0,bytes);')
add('cudnnConvolutionForward',D,
    'cudnnHandle_t handle,const void *alpha,cudnnTensorDescriptor_t xd,const void *input,cudnnFilterDescriptor_t wd,const void *weights,cudnnConvolutionDescriptor_t cd,cudnnConvolutionFwdAlgo_t algo,void *workspace,size_t bytes,const void *beta,cudnnTensorDescriptor_t yd,void *output',
    'if(!alpha||!beta) BAD;'+tuple_guest+'PUT(5,algo);PUT(6,bytes);memcpy(p+56,alpha,4);memcpy(p+64,beta,4);REF(9,input,0);REF(11,weights,0);REF(13,output,0);REF(15,workspace,bytes);',
    tuple_worker+'if(A(5)>=CUDNN_CONVOLUTION_FWD_ALGO_COUNT) BAD;size_t required=0;rc=cudnnGetConvolutionForwardWorkspaceSize(h,x,w,c,y,A(5),&required);if(rc)break;if(A(6)<required) BAD;DEV(9,tensor_bytes(x),0,input);DEV(11,filter_bytes(w),0,weights);DEV(13,tensor_bytes(y),0,output);DEV(15,A(6),A(6)==0,workspace);float alpha,beta;memcpy(&alpha,p+56,4);memcpy(&beta,p+64,4);rc=cudnnConvolutionForward(h,&alpha,x,input,w,weights,c,A(5),workspace,A(6),&beta,y,output);')
