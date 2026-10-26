import ctypes as C,time,json
from pathlib import Path
x=C.CDLL('/opt/vmweave/lib/libvmweave_guest.so');P=C.c_void_p
x.cudaMalloc.argtypes=[C.POINTER(P),C.c_size_t];x.cudaMemcpy.argtypes=[P,P,C.c_size_t,C.c_int]
n=16*1024*1024;d=P();src=C.create_string_buffer(n)
assert x.cudaMalloc(C.byref(d),n)==0
assert x.cudaMemcpy(d,src,n,1)==0
Path('/tmp/fault-ready').touch()
while not Path('/tmp/fault-go').exists():time.sleep(.02)
Path('/tmp/fault-submitting').touch();start=time.monotonic();rc=x.cudaMemcpy(d,src,n,1);second=x.cudaMemcpy(d,src,n,1)
result={'first':rc,'second':second,'seconds':time.monotonic()-start}
Path('/tmp/fault-result.json').write_text(json.dumps(result));assert rc!=0 and second!=0,result
