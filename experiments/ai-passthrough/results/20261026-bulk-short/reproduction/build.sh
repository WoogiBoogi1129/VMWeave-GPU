set -eu
S=/work/experiments/ai-passthrough/results/20261026-bulk-short/src
B=/work/.local/bulk-short-20261026
C='/usr/local/cuda/bin/nvcc -O3 -arch=sm_90 --cudart=shared'
$C -I"$S" "$S/nw/needle.cu" -o "$B/nw"
gcc -O3 -c "$S/lud/common/common.c" -o "$B/common.o"
$C -I"$S" -I"$S/lud/common" "$S/lud/cuda/lud.cu" "$S/lud/cuda/lud_kernel.cu" "$B/common.o" -o "$B/lu"
$C -I"$S" "$S/srad/srad_v2/srad.cu" -o "$B/srad"
$C -I"$S" "$S/streamcluster/streamcluster_cuda_cpu.cpp" "$S/streamcluster/streamcluster_cuda.cu" -o "$B/sc"
