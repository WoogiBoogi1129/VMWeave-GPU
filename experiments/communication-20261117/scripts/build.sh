set -eu
cd /work
src=experiments/communication-20261117/src
out=.local/communication-20261117/artifacts
cc -O2 -I/usr/local/cuda/include "$src/probe.c" -L/usr/local/cuda/lib64 -L/usr/local/cuda/lib64/stubs -lcudart -lcuda -o "$out/N/probe"
cc -O2 -DVMWEAVE -I/usr/local/cuda/include "$src/probe.c" -L"$out/V" -lvmweave_guest -Wl,-rpath,'$ORIGIN' -o "$out/V/probe"
cc -O2 -DFLYT_TCP -Wl,--allow-shlib-undefined -I/usr/local/cuda/include "$src/probe.c" -L"$out/F" -Wl,-rpath,'$ORIGIN' -l:cricket-client.so -o "$out/F/probe"
/usr/local/cuda/bin/ptxas -arch=sm_120 "$src/sequence.ptx" -o "$out/sequence-original.cubin"
cp -L /usr/local/cuda/lib64/libcudart.so.12 "$out/N/"
