"""Build the frozen experiment sources; requires CUDA12.8 toolkit and gcc."""
import argparse,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--nvcc',default='nvcc');p.add_argument('--cc',default='gcc');p.add_argument('--arch',default='sm_90');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
s=Path(__file__).resolve().parents[1]/'src';b=a.output.resolve();b.mkdir(parents=True,exist_ok=True)
def run(args):subprocess.run(list(map(str,args)),check=True)
c=[a.nvcc,'-O3','-arch='+a.arch,'--cudart=shared','-I'+str(s)]
run([a.cc,'-O3','-c',s/'lud/common/common.c','-o',b/'common.o'])
for name,extra in [('nw',[s/'nw/needle.cu']),('lu',['-I'+str(s/'lud/common'),s/'lud/cuda/lud.cu',s/'lud/cuda/lud_kernel.cu',b/'common.o']),('srad',[s/'srad/srad_v2/srad.cu']),('sc',[s/'streamcluster/streamcluster_cuda_cpu.cpp',s/'streamcluster/streamcluster_cuda.cu'])]:run(c+extra+['-o',b/name])
