"""Supplementary hypothesis test: physical memory at the post-training quota boundary.
Runs the identical training workload, then adds direct CUDA allocations outside
PyTorch's caching allocator. This is separate from the predeclared 10 repeats.
"""
from pathlib import Path
source=Path(__file__).with_name('torch_accounting.py').read_text()
extra='''
import ctypes,math
cuda=ctypes.CDLL('/tmp/perf/libflyt_guest.so')
cuda.cudaMalloc.argtypes=[ctypes.POINTER(ctypes.c_void_p),ctypes.c_size_t]
cuda.cudaFree.argtypes=[ctypes.c_void_p]
cuda.cudaMemset.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_size_t]
cuda.cudaMemcpy.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int]
def checked(rc):
 if rc:raise RuntimeError('CUDA operation failed: '+str(rc))
reported_free,total=torch.cuda.mem_get_info();free=reported_free//4096*4096;assert free>0
candidate=ctypes.c_void_p();over=cuda.cudaMalloc(ctypes.byref(candidate),free+4096);assert over==2
stage('trained-min-fail',direct_requested=free+4096,api_rc=over,reported_free_before=reported_free)
ptr=ctypes.c_void_p();checked(cuda.cudaMalloc(ctypes.byref(ptr),free));checked(cuda.cudaMemset(ptr,0x5a,free));checked(cuda.cudaDeviceSynchronize())
# Whole-buffer memset and synchronization, plus head/middle/tail samples. Not full-buffer verification.
for offset in [0,free//2,free-16]:
 data=(ctypes.c_ubyte*16)();checked(cuda.cudaMemcpy(data,ctypes.c_void_p(ptr.value+offset),16,2));assert bytes(data)==b'Z'*16
stage('trained-max',direct_requested=free,api_rc=0,sampled_bytes=48)
candidate=ctypes.c_void_p();over=cuda.cudaMalloc(ctypes.byref(candidate),4096);assert over==2
stage('trained-extra-oom',direct_requested=free,extra_requested=4096,api_rc=over)
checked(cuda.cudaFree(ptr));stage('trained-direct-free',direct_requested=0,api_rc=0)
opt.zero_grad(set_to_none=True);loss=torch.nn.functional.mse_loss(net(x),y);loss.backward();opt.step();torch.cuda.synchronize()
recovery_loss=loss.detach().cpu().item();assert math.isfinite(recovery_loss)
stage('trained-recovery',loss=recovery_loss)
'''
assert source.count('del loss,opt,x,y,net;')==1
exec(compile(source.replace('del loss,opt,x,y,net;',extra+'\ndel loss,opt,x,y,net;'),str(Path(__file__)), 'exec'))
