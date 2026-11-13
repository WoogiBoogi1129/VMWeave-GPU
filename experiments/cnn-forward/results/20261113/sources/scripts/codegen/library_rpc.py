from pathlib import Path
BASE=Path(__file__).resolve().parent
root=BASE.parents[1]/'runtime/shm'
# Explicit field schema; host pointers never cross the transport.
IDS = {
    'cudnnCreateTensorDescriptor': 0x3300,
    'cudnnDestroyTensorDescriptor': 0x3301,
    'cudnnCreateDropoutDescriptor': 0x3302,
    'cudnnDestroyDropoutDescriptor': 0x3303,
    'cudnnCreateRNNDescriptor': 0x3304,
    'cudnnDestroyRNNDescriptor': 0x3305,
    'cudnnCreateRNNDataDescriptor': 0x3306,
    'cudnnDestroyRNNDataDescriptor': 0x3307,
    'cudnnSetStream': 0x3308,
    'cudnnGetStream': 0x3309,
    'cudnnSetTensorNdDescriptor': 0x330a,
    'cudnnGetTensorNdDescriptor': 0x330b,
    'cudnnSetDropoutDescriptor': 0x330c,
    'cudnnRestoreDropoutDescriptor': 0x330d,
    'cudnnDropoutGetStatesSize': 0x330e,
    'cudnnSetRNNDescriptor_v8': 0x330f,
    'cudnnSetRNNDataDescriptor': 0x3310,
    'cudnnGetRNNWeightSpaceSize': 0x3311,
    'cudnnGetRNNTempSpaceSizes': 0x3312,
    'cudnnGetRNNWeightParams': 0x3313,
    'cudnnRNNForward': 0x3314,
    'cudnnRNNBackwardData_v8': 0x3315,
    'cudnnRNNBackwardWeights_v8': 0x3316,
    'cublasLtCreate': 0x3317,
    'cublasLtDestroy': 0x3318,
    'cublasLtMatrixLayoutDestroy': 0x3319,
    'cublasLtMatmulDescDestroy': 0x331a,
    'cublasLtMatmulPreferenceDestroy': 0x331b,
    'cublasLtMatrixLayoutCreate': 0x331c,
    'cublasLtMatmulDescCreate': 0x331d,
    'cublasLtMatmulPreferenceCreate': 0x331e,
    'cublasLtMatmulDescSetAttribute': 0x331f,
    'cublasLtMatmulPreferenceSetAttribute': 0x3320,
    'cublasLtMatmulAlgoGetHeuristic': 0x3321,
    'cublasLtMatmul': 0x3322,
}
ops=[]
def add(name,ret,args,g,w):ops.append((name,ret,args,g,w))
D='cudnnStatus_t'; B='cublasStatus_t'
for name,typ,kind in [('Tensor','cudnnTensorDescriptor_t','TENSOR'),('Dropout','cudnnDropoutDescriptor_t','DROPOUT'),('RNN','cudnnRNNDescriptor_t','RNN'),('RNNData','cudnnRNNDataDescriptor_t','RNNDATA')]:
 add('cudnnCreate'+name+'Descriptor',D,f'{typ} *desc','if(!desc) BAD;','void *v=NULL; rc=cudnnCreate'+name+'Descriptor(('+typ+'*)&v); if(!rc) rc=save_object('+kind+',v,out);')
 # guest output
 ops[-1]=(*ops[-1][:3],ops[-1][3]+'\nAFTER(*desc=('+typ+')(uintptr_t)GET(0));',ops[-1][4])
 add('cudnnDestroy'+name+'Descriptor',D,f'{typ} desc','PUT(0,desc);',f'OBJ(0,{kind},d); rc=cudnnDestroy{name}Descriptor(d); if(!rc) drop_object(A(0));')
add('cudnnSetStream',D,'cudnnHandle_t handle, cudaStream_t stream','PUT(0,handle);PUT(1,stream);','DNN(0,h); STREAM(1,st); rc=cudnnSetStream(h,st);')
add('cudnnGetStream',D,'cudnnHandle_t handle, cudaStream_t *stream','if(!stream) BAD; PUT(0,handle); AFTER(*stream=(cudaStream_t)(uintptr_t)GET(0));','DNN(0,h); cudaStream_t st; rc=cudnnGetStream(h,&st); if(!rc){uint64_t id;if(!vmweave_async_stream_id(st,&id)) BAD; OUT(0,id);}')
add('cudnnSetTensorNdDescriptor',D,'cudnnTensorDescriptor_t desc, cudnnDataType_t type, int n, const int dims[], const int strides[]',
'if(n<1||n>8||!dims||!strides) BAD; PUT(0,desc);PUT(1,type);PUT(2,n); for(int i=0;i<n;i++){PUT(3+i,dims[i]);PUT(11+i,strides[i]);}',
'OBJ(0,TENSOR,d); int n=A(2),dims[8],strides[8];if(n<1||n>8) BAD;for(int i=0;i<n;i++){dims[i]=A(3+i);strides[i]=A(11+i);} rc=cudnnSetTensorNdDescriptor(d,A(1),n,dims,strides);')
add('cudnnGetTensorNdDescriptor',D,'cudnnTensorDescriptor_t desc, int requested, cudnnDataType_t *type, int *n, int dims[], int strides[]',
'if(requested<1||requested>8||!type||!n||!dims||!strides) BAD; PUT(0,desc);PUT(1,requested); AFTER(*type=GET(0);*n=GET(1);for(int i=0;i<requested;i++){dims[i]=GET(2+i);strides[i]=GET(10+i);});',
'OBJ(0,TENSOR,d);int req=A(1),n=0,dims[8]={0},strides[8]={0};cudnnDataType_t type;if(req<1||req>8) BAD;rc=cudnnGetTensorNdDescriptor(d,req,&type,&n,dims,strides);if(!rc){OUT(0,type);OUT(1,n);for(int i=0;i<req;i++){OUT(2+i,dims[i]);OUT(10+i,strides[i]);}}')
for fn in ['cudnnSetDropoutDescriptor','cudnnRestoreDropoutDescriptor']:
 add(fn,D,'cudnnDropoutDescriptor_t desc, cudnnHandle_t handle, float dropout, void *states, size_t bytes, unsigned long long seed',
 'PUT(0,desc);PUT(1,handle);memcpy(p+16,&dropout,4);PUT(3,bytes);PUT(4,seed);REF(5,states,bytes);',
 f'OBJ(0,DROPOUT,d);DNN(1,h);float dropout;memcpy(&dropout,p+16,4);DEV(5,A(3),A(3)==0,states);rc={fn}(d,h,dropout,states,A(3),A(4));')
add('cudnnDropoutGetStatesSize',D,'cudnnHandle_t handle,size_t *bytes','if(!bytes) BAD;PUT(0,handle);AFTER(*bytes=GET(0));','DNN(0,h);size_t bytes;rc=cudnnDropoutGetStatesSize(h,&bytes);if(!rc)OUT(0,bytes);')
args='cudnnRNNDescriptor_t desc,cudnnRNNAlgo_t algo,cudnnRNNMode_t mode,cudnnRNNBiasMode_t bias,cudnnDirectionMode_t direction,cudnnRNNInputMode_t input,cudnnDataType_t type,cudnnDataType_t precision,cudnnMathType_t math,int32_t inputSize,int32_t hiddenSize,int32_t projSize,int32_t layers,cudnnDropoutDescriptor_t dropout,uint32_t flags'
add('cudnnSetRNNDescriptor_v8',D,args,''.join(f'PUT({i},{x});' for i,x in enumerate(['desc','algo','mode','bias','direction','input','type','precision','math','inputSize','hiddenSize','projSize','layers','dropout','flags'])),
 'OBJ(0,RNN,d);OBJ(13,DROPOUT,drop);rc=cudnnSetRNNDescriptor_v8(d,A(1),A(2),A(3),A(4),A(5),A(6),A(7),A(8),A(9),A(10),A(11),A(12),drop,A(14));')
add('cudnnSetRNNDataDescriptor',D,'cudnnRNNDataDescriptor_t desc,cudnnDataType_t type,cudnnRNNDataLayout_t layout,int seq,int batch,int vector,const int lengths[],void *padding',
 'if(batch<1||batch>1024||!lengths||type!=CUDNN_DATA_FLOAT||layout==CUDNN_RNN_DATA_LAYOUT_SEQ_MAJOR_PACKED) UNSUP;PUT(0,desc);PUT(1,type);PUT(2,layout);PUT(3,seq);PUT(4,batch);PUT(5,vector);PUT(6,padding!=NULL);if(padding)memcpy(p+56,padding,4);for(int i=0;i<batch;i++)vmweave_put(p+512+4*i,lengths[i],4);',
 'OBJ(0,RNNDATA,d);int batch=A(4),lengths[1024];if(batch<1||batch>1024||A(1)!=CUDNN_DATA_FLOAT||A(2)==CUDNN_RNN_DATA_LAYOUT_SEQ_MAJOR_PACKED) UNSUP;for(int i=0;i<batch;i++)lengths[i]=vmweave_get(p+512+4*i,4);float padding;memcpy(&padding,p+56,4);rc=cudnnSetRNNDataDescriptor(d,A(1),A(2),A(3),batch,A(5),lengths,A(6)?&padding:NULL); if(!rc){size_t bytes;if(!checked_rnn_bytes(A(3),A(4),A(5),&bytes)) BAD;object_size(A(0),bytes);}')
add('cudnnGetRNNWeightSpaceSize',D,'cudnnHandle_t handle,cudnnRNNDescriptor_t desc,size_t *bytes','if(!bytes) BAD;PUT(0,handle);PUT(1,desc);AFTER(*bytes=GET(0));','DNN(0,h);OBJ(1,RNN,d);size_t bytes;rc=cudnnGetRNNWeightSpaceSize(h,d,&bytes);if(!rc)OUT(0,bytes);')
add('cudnnGetRNNTempSpaceSizes',D,'cudnnHandle_t handle,cudnnRNNDescriptor_t desc,cudnnForwardMode_t mode,cudnnRNNDataDescriptor_t xdesc,size_t *workspace,size_t *reserve',
 'if(!workspace&&!reserve) BAD;PUT(0,handle);PUT(1,desc);PUT(2,mode);PUT(3,xdesc);AFTER(if(workspace)*workspace=GET(0);if(reserve)*reserve=GET(1));',
 'DNN(0,h);OBJ(1,RNN,d);OBJ(3,RNNDATA,x);size_t w,r;rc=cudnnGetRNNTempSpaceSizes(h,d,A(2),x,&w,&r);if(!rc){OUT(0,w);OUT(1,r);}')
add('cudnnGetRNNWeightParams',D,'cudnnHandle_t handle,cudnnRNNDescriptor_t desc,int32_t layer,size_t bytes,const void *weights,int32_t linear,cudnnTensorDescriptor_t mdesc,void **matrix,cudnnTensorDescriptor_t bdesc,void **bias',
 'if((mdesc&&!matrix)||(bdesc&&!bias)) BAD;PUT(0,handle);PUT(1,desc);PUT(2,layer);PUT(3,bytes);REF(4,weights,bytes);PUT(6,linear);PUT(7,mdesc);PUT(8,bdesc);AFTER(if(matrix)*matrix=GET(0)==UINT64_MAX?NULL:(void*)((uintptr_t)weights+GET(0));if(bias)*bias=GET(1)==UINT64_MAX?NULL:(void*)((uintptr_t)weights+GET(1)));',
 'DNN(0,h);OBJ(1,RNN,d);DEV(4,A(3),0,w);void *md=NULL,*bd=NULL,*mp=NULL,*bp=NULL;if(A(7)){md=get_object(A(7),TENSOR);if(!md) BAD;}if(A(8)){bd=get_object(A(8),TENSOR);if(!bd) BAD;}rc=cudnnGetRNNWeightParams(h,d,A(2),A(3),w,A(6),md,md?&mp:NULL,bd,bd?&bp:NULL);if(!rc){if((mp&&((uintptr_t)mp<(uintptr_t)w||(uintptr_t)mp-(uintptr_t)w>=A(3)))||(bp&&((uintptr_t)bp<(uintptr_t)w||(uintptr_t)bp-(uintptr_t)w>=A(3)))) BAD;OUT(0,mp?(uintptr_t)mp-(uintptr_t)w:UINT64_MAX);OUT(1,bp?(uintptr_t)bp-(uintptr_t)w:UINT64_MAX);}')
# Execution functions: descriptors supply required allocation spans, never trust raw GPU VAs.
add('cudnnRNNForward',D,'cudnnHandle_t handle,cudnnRNNDescriptor_t rnn,cudnnForwardMode_t mode,const int32_t lengths[],cudnnRNNDataDescriptor_t xd,const void *x,cudnnRNNDataDescriptor_t yd,void *y,cudnnTensorDescriptor_t hd,const void *hx,void *hy,cudnnTensorDescriptor_t cd,const void *cx,void *cy,size_t wb,const void *w,size_t sb,void *ws,size_t rb,void *rs',
 'if(lengths) UNSUP;PUT(0,handle);PUT(1,rnn);PUT(2,mode);PUT(3,xd);PUT(4,yd);PUT(5,hd);PUT(6,cd);PUT(7,wb);PUT(8,sb);PUT(9,rb);REF(10,x,0);REF(12,y,0);REF(14,hx,0);REF(16,hy,0);REF(18,cx,0);REF(20,cy,0);REF(22,w,wb);REF(24,ws,sb);REF(26,rs,rb);',
 'DNN(0,h);OBJ(1,RNN,r);OBJ(3,RNNDATA,xd);OBJ(4,RNNDATA,yd);OBJ(5,TENSOR,hd);OBJ(6,TENSOR,cd);DEV(10,object_bytes(A(3)),0,x);DEV(12,object_bytes(A(4)),0,y);DEV(14,tensor_bytes(hd),1,hx);DEV(16,tensor_bytes(hd),1,hy);DEV(18,tensor_bytes(cd),1,cx);DEV(20,tensor_bytes(cd),1,cy);DEV(22,A(7),0,w);DEV(24,A(8),A(8)==0,ws);DEV(26,A(9),A(9)==0,rs);rc=cudnnRNNForward(h,r,A(2),NULL,xd,x,yd,y,hd,hx,hy,cd,cx,cy,A(7),w,A(8),ws,A(9),rs);')
add('cudnnRNNBackwardData_v8',D,'cudnnHandle_t handle,cudnnRNNDescriptor_t rnn,const int32_t lengths[],cudnnRNNDataDescriptor_t yd,const void *y,const void *dy,cudnnRNNDataDescriptor_t xd,void *dx,cudnnTensorDescriptor_t hd,const void *hx,const void *dhy,void *dhx,cudnnTensorDescriptor_t cd,const void *cx,const void *dcy,void *dcx,size_t wb,const void *w,size_t sb,void *ws,size_t rb,void *rs',
 'if(lengths) UNSUP;PUT(0,handle);PUT(1,rnn);PUT(3,xd);PUT(4,yd);PUT(5,hd);PUT(6,cd);PUT(7,wb);PUT(8,sb);PUT(9,rb);REF(10,y,0);REF(12,dy,0);REF(14,dx,0);REF(16,hx,0);REF(18,dhy,0);REF(20,dhx,0);REF(22,cx,0);REF(24,dcy,0);REF(26,dcx,0);REF(28,w,wb);REF(30,ws,sb);REF(32,rs,rb);',
 'DNN(0,h);OBJ(1,RNN,r);OBJ(3,RNNDATA,xd);OBJ(4,RNNDATA,yd);OBJ(5,TENSOR,hd);OBJ(6,TENSOR,cd);DEV(10,object_bytes(A(4)),0,y);DEV(12,object_bytes(A(4)),0,dy);DEV(14,object_bytes(A(3)),0,dx);DEV(16,tensor_bytes(hd),1,hx);DEV(18,tensor_bytes(hd),1,dhy);DEV(20,tensor_bytes(hd),1,dhx);DEV(22,tensor_bytes(cd),1,cx);DEV(24,tensor_bytes(cd),1,dcy);DEV(26,tensor_bytes(cd),1,dcx);DEV(28,A(7),0,w);DEV(30,A(8),A(8)==0,ws);DEV(32,A(9),A(9)==0,rs);rc=cudnnRNNBackwardData_v8(h,r,NULL,yd,y,dy,xd,dx,hd,hx,dhy,dhx,cd,cx,dcy,dcx,A(7),w,A(8),ws,A(9),rs);')
add('cudnnRNNBackwardWeights_v8',D,'cudnnHandle_t handle,cudnnRNNDescriptor_t rnn,cudnnWgradMode_t mode,const int32_t lengths[],cudnnRNNDataDescriptor_t xd,const void *x,cudnnTensorDescriptor_t hd,const void *hx,cudnnRNNDataDescriptor_t yd,const void *y,size_t wb,void *w,size_t sb,void *ws,size_t rb,void *rs',
 'if(lengths) UNSUP;PUT(0,handle);PUT(1,rnn);PUT(2,mode);PUT(3,xd);PUT(4,yd);PUT(5,hd);PUT(7,wb);PUT(8,sb);PUT(9,rb);REF(10,x,0);REF(12,y,0);REF(14,hx,0);REF(16,w,wb);REF(18,ws,sb);REF(20,rs,rb);',
 'DNN(0,h);OBJ(1,RNN,r);OBJ(3,RNNDATA,xd);OBJ(4,RNNDATA,yd);OBJ(5,TENSOR,hd);DEV(10,object_bytes(A(3)),0,x);DEV(12,object_bytes(A(4)),0,y);DEV(14,tensor_bytes(hd),1,hx);DEV(16,A(7),0,w);DEV(18,A(8),A(8)==0,ws);DEV(20,A(9),A(9)==0,rs);rc=cudnnRNNBackwardWeights_v8(h,r,A(2),NULL,xd,x,hd,hx,yd,y,A(7),w,A(8),ws,A(9),rs);')
exec((BASE/'library_lt.py').read_text())
exec((BASE/'library_conv.py').read_text())
# Generated C files use explicit byte encoding, bounded messages, typed session-local handles.
guest='''/* Generated by scripts/codegen/library_rpc.py; edit the schema there. */
#include "vmweave_guest.h"
#include "vmweave_library.h"
#include <cudnn.h>
#include <cublasLt.h>
#include <string.h>
#define PUT(i,v) vmweave_put(p+8*(i),(uint64_t)(uintptr_t)(v),8)
#define GET(i) vmweave_get(out+8*(i),8)
#define BAD do{rc=bad;goto done;}while(0)
#define UNSUP do{rc=unsupported;goto done;}while(0)
#define REF(i,ptr,n) do {struct vmweave_device_ref ref={0};if(ptr){if(vmweave_guest_ref(ptr,n,&ref)) BAD;}else if(n) BAD;PUT(i,ref.handle);PUT((i)+1,ref.offset);}while(0)
'''
worker=(BASE/'library_worker.inc').read_text()
header='''#ifndef VMWEAVE_LIBRARY_H
#define VMWEAVE_LIBRARY_H
#include "vmweave_compat.h"
#define VMWEAVE_LIBRARY_REQUEST 4608u
#define VMWEAVE_LIBRARY_RESPONSE 512u
void *vmweave_compat_dnn(uint64_t id);
void *vmweave_compat_blas(uint64_t id);
int vmweave_async_stream_id(void *stream,uint64_t *id);
int vmweave_library_dispatch(struct vmweave_cuda_session *,const struct vmweave_shm_request *,struct vmweave_shm_response *);
int vmweave_library_close(void);
enum {\n'''
worker+='''int vmweave_library_dispatch(struct vmweave_cuda_session *s,const struct vmweave_shm_request *q,struct vmweave_shm_response *response){
const uint8_t *p=q->input;uint8_t *out=response->output;int rc=CUDNN_STATUS_BAD_PARAM,bad_value=CUDNN_STATUS_BAD_PARAM,unsupported_value=CUDNN_STATUS_NOT_SUPPORTED;
response->output_bytes=0;response->transport_status=0;response->result_domain=VMWEAVE_RESULT_LIBRARY;
if(q->payload_schema!=1||q->input_bytes!=VMWEAVE_LIBRARY_REQUEST||!p||!out||response->output_capacity<VMWEAVE_LIBRARY_RESPONSE){response->transport_status=VMWEAVE_SHM_BAD_DESCRIPTOR;return 0;}
memset(out,0,VMWEAVE_LIBRARY_RESPONSE);
switch(q->api_id){\n'''
for i,(name,ret,args,g,w) in enumerate(ops):
 api='VMWEAVE_LIB_'+name;header+=f'{api}=0x{IDS[name]:x},\n'
 bad='CUDNN_STATUS_BAD_PARAM' if ret==D else 'CUBLAS_STATUS_INVALID_VALUE';unsupported='CUDNN_STATUS_NOT_SUPPORTED' if ret==D else 'CUBLAS_STATUS_NOT_SUPPORTED'
 after=''
 if 'AFTER(' in g:
  start=g.index('AFTER(');end=g.rindex(');');after=g[start+6:end]+';';g=g[:start]+g[end+2:]
 guest+=f'{ret} {name}({args}){{\n uint8_t p[VMWEAVE_LIBRARY_REQUEST]={{0}},out[VMWEAVE_LIBRARY_RESPONSE];size_t got=0;int rc=0,bad={bad},unsupported={unsupported};pthread_mutex_lock(&vmweave_guest_lock);\n {g}\n rc=vmweave_guest_exchange({api},p,sizeof(p),out,sizeof(out),&got);\n if(rc==999)rc='+('CUDNN_STATUS_INTERNAL_ERROR' if ret==D else 'CUBLAS_STATUS_INTERNAL_ERROR')+';else if(rc==801)rc=unsupported;\n if(!rc){if(got!=sizeof(out)){rc=bad;goto done;}'+after+'}\n done:pthread_mutex_unlock(&vmweave_guest_lock);return rc;\n}\n'
 worker+=f'case {api}:{{bad_value={bad};unsupported_value={unsupported};{w} break;}}\n'
worker+='''default: response->transport_status=VMWEAVE_SHM_UNSUPPORTED_API;return 0;
} goto done;
bad:rc=bad_value;goto done;
unsupported:rc=unsupported_value;
done:response->api_result=rc;if(!rc)response->output_bytes=VMWEAVE_LIBRARY_RESPONSE;
if(getenv("VMWEAVE_LIBRARY_TRACE"))fprintf(stderr,"library api=%u result=%d\\n",q->api_id,rc);
return 0;
}
'''
header+='};\n#endif\n'
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
for name,text in [('src/guest_library.c',guest),('src/library.c',worker),('include/vmweave_library.h',header)]:
 path=root/name
 if args.check:
  if path.read_text()!=text:raise SystemExit('outdated generated file: '+str(path))
 else:path.write_text(text)

