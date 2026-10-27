"""Exercise the built Guest's real TLS state without a CUDA device or transport."""
import ctypes as C
from pathlib import Path
import threading

lib=C.CDLL(str(Path(__file__).resolve().parents[1]/'build/libvmweave_guest.so'))
record=lib.vmweave_guest_record_error;record.argtypes=[C.c_int];record.restype=C.c_int
peek=lib.cudaPeekAtLastError;get=lib.cudaGetLastError
assert get()==0 and record(1)==1 and peek()==1
assert record(0)==0 and peek()==1
results=[]
def other_thread():
    results.extend([peek(),record(700),peek(),get(),peek()])
t=threading.Thread(target=other_thread);t.start();t.join()
assert results==[0,700,700,700,0],results
assert peek()==1 and get()==1 and peek()==0
print('PASS native memset sticky errors, return value, get/peek reset, thread isolation')
