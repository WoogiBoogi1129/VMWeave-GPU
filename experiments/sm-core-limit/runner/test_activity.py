"""Exercise actual candidate idle predicate and throttled-launch activity code."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[3]
s=(root/'.local/sm-core-limit-20261015/HAMi-core/src/multiprocess/multiprocess_utilization_watcher.c').read_text()
predicate=s[s.index('static int device_is_idle('):s.index('extern int pidfound;')]
limiter=s[s.index('void rate_limiter('):s.index('static void change_token(')]
c='''#include <stdint.h>
#include <assert.h>
#include <time.h>
typedef int CUdevice;
typedef int CUresult;
#define CUDA_SUCCESS 0
#define CAS(p,a,b) __sync_bool_compare_and_swap(p,a,b)
static uint64_t g_last_activity_ns[1];
static volatile int64_t g_cur_cuda_cores[1];
static int cached_sm_limit[1],cached_util_switch;
static struct timespec g_cycle;
static uint64_t fake_now=3000000000ULL;
static int sleeps;
static uint64_t monotonic_ns(void){return fake_now;}
static int cuCtxGetDevice(int *d){*d=0;return 0;}
static int get_recent_kernel(void){return 0;}
static void set_recent_kernel(int n){(void)n;}
static unsigned sleep(unsigned n){return n;}
static int fake_nanosleep(const struct timespec *a, struct timespec *b){
 (void)a;(void)b;sleeps++;fake_now+=100000000ULL;g_cur_cuda_cores[0]=100;return 0;
}
#define nanosleep fake_nanosleep
'''+predicate+limiter+'''
int main(void){
 assert(device_is_idle(0,0,fake_now));
 assert(!device_is_idle(0,50,fake_now));
 cached_sm_limit[0]=100;cached_util_switch=1;
 rate_limiter(10,1);assert(g_last_activity_ns[0]==0);
 cached_sm_limit[0]=50;g_cur_cuda_cores[0]=-1;
 rate_limiter(10,1);
 assert(sleeps==1);assert(g_cur_cuda_cores[0]==90);
 assert(g_last_activity_ns[0]==fake_now);
 assert(!device_is_idle(0,0,fake_now));
 assert(!device_is_idle(0,0,fake_now+1000000000ULL));
 assert(device_is_idle(0,0,fake_now+1000000001ULL));
 assert(!device_is_idle(0,1,fake_now+1000000001ULL));
 return 0;
}
'''
with tempfile.TemporaryDirectory() as d:
    p=Path(d);(p/'test.c').write_text(c)
    subprocess.run(['gcc','-Wall','-Werror','-fsanitize=undefined',str(p/'test.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
print('PASS: actual idle predicate, 100% fast path, throttled producer liveness, timeout boundary')
