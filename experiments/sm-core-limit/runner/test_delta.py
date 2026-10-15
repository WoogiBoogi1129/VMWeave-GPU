"""Compile the actual patched delta function and exercise scaling and saturation."""
from pathlib import Path
import subprocess, tempfile
root=Path(__file__).resolve().parents[3]
source=(root/'.local/sm-core-limit-20261015/HAMi-core/src/multiprocess/multiprocess_utilization_watcher.c').read_text()
function=source[source.index('static int64_t delta('):source.index('unsigned int nvml_to_cuda_map(')]
program='''#include <stdint.h>
#include <stdlib.h>
#include <assert.h>
#include <math.h>
static int g_sm_num[2],g_max_thread_per_sm[2];
static int64_t g_total_cuda_cores[2];
'''+function+'''
int main(void) {
 g_sm_num[0]=20;g_sm_num[1]=188;
 for(int i=0;i<2;i++) {
  g_max_thread_per_sm[i]=1536;
  g_total_cuda_cores[i]=(int64_t)g_sm_num[i]*1536*32;
  assert(delta(50,100,0,i)==0);
  assert(delta(50,0,g_total_cuda_cores[i],i)==g_total_cuda_cores[i]);
  assert(delta(50,40,100000,i)>100000);
  assert(delta(50,60,100000,i)<100000);
 }
 double a=(double)delta(50,40,0,0)/g_total_cuda_cores[0];
 double b=(double)delta(50,40,0,1)/g_total_cuda_cores[1];
 assert(fabs(a-b)<1e-7);
 return 0;
}
'''
with tempfile.TemporaryDirectory() as d:
    p=Path(d);(p/'test.c').write_text(program)
    subprocess.run(['gcc','-Wall','-Werror','-fsanitize=undefined',str(p/'test.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
print('PASS: actual delta scaling, direction, saturation; UBSan enabled')
