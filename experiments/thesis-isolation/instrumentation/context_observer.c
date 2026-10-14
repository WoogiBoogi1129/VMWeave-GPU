/* Passive observer: forwards unchanged launch arguments, records current context. */
#define _GNU_SOURCE
#include <cuda.h>
#include <dlfcn.h>
#include <stdio.h>
#include <unistd.h>
CUresult cuLaunchKernel(CUfunction f,unsigned gx,unsigned gy,unsigned gz,unsigned bx,unsigned by,unsigned bz,unsigned shared,CUstream stream,void **args,void **extra){
 typedef CUresult (*launch_fn)(CUfunction,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,CUstream,void**,void**);
 launch_fn next=(launch_fn)dlsym(RTLD_NEXT,"cuLaunchKernel");
 CUresult (*current)(CUcontext*)=(void*)dlsym(RTLD_NEXT,"cuCtxGetCurrent");
 CUcontext ctx=NULL;int ce=current?current(&ctx):999;
 if(!next)return CUDA_ERROR_UNKNOWN;
 CUresult result=next(f,gx,gy,gz,bx,by,bz,shared,stream,args,extra);
 fprintf(stderr,"BOUNDARY_CONTEXT {\"pid\":%ld,\"context\":\"%p\",\"context_query\":%d,\"launch\":%d}\n",(long)getpid(),(void*)ctx,ce,(int)result);
 return result;
}
