Build the frozen final experiment sources using build.py --output PATH.
CUDA 12.8.93, gcc and a compatible NVIDIA driver/GPU are required.
Use --nvcc /usr/local/cuda/bin/nvcc when nvcc is not on PATH.
The captured environment compiled with sm_90 plus embedded PTX on Blackwell.
EXPERIMENT_REPEATS=2 means two warmups followed by two measured repetitions.
EXPERIMENT_SAMPLE JSON lines are the timing authority; original printed GPU
or application timers are not used. Dumped output must match reference hashes.

preparation-history contains exploratory preparation scripts, not a generator
for the final source tree: additional reviewed adaptation is present in src/.
The CPU SRAD reference is a separate correctness check, not a measured mode.
Cluster harness scripts depend on this installation's VM image, driver payload,
Guest credentials and local images. Do not run them blindly on another cluster.
No private key, kubeconfig or database password is published.

StreamCluster CUDATIME is disabled in the frozen source in every mode.
The internal GPU-event profiler (including its event waits) is not supported by
the current VMWeave Guest. Earlier SC results are archived under excluded/
and must not be mixed with the final SC samples. Algorithm/input are unchanged.
