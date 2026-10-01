# First SHM implementation bundle — actual VM ablation

This harness is derived from the completed performance campaign but writes only
to `.local/shm-first-20261001` and `experiments/evidence/results/2026-10-01-shm-first`.
The September campaign remains immutable. Testbed-specific node, GPU UUID and
images are recorded in `common.py`; use a dedicated testbed before reproducing.

Four configurations use identical rebuilt Guest/Worker binaries, HAMi FORCE 100,
the same probe, CPU affinity, VM image, CUDA work and protocol. They independently
select legacy/short wait and legacy/optimized copies. Every formal repetition
uses a fresh VM/channel/Worker and output validation. Pilot runs are separate.

The initial 20µs spin pilot showed substantial speedup but high saturated CPU
use. `build_sleep.py` creates zero-spin candidates using the same binary. Active
spinning remains configurable, but the formal candidate is selected only after
the zero-spin pilot. Short sleeps and idle backoff are not event-driven wakeups.

Preparation: build `runtime/shm` with CUDA 12.8 and the same build container as
the recorded campaign, install the Worker/Guest artifacts under the private
directory, and provision the existing probe, PTX and SSH keys there. Build flags,
actual commands and artifact hashes are retained in the result bundle. Private
keys must never be copied to the public bundle.

```sh
python3 experiments/shm-first-bundle/build_images.py
python3 experiments/shm-first-bundle/run.py pilot
python3 experiments/shm-first-bundle/build_sleep.py
python3 experiments/shm-first-bundle/run.py pilot-zero
# Review pilot correctness, latency and CPU before formal selection.
python3 experiments/shm-first-bundle/run.py formal
python3 experiments/shm-first-bundle/analyze.py
python3 experiments/shm-first-bundle/analyze_cpu.py
python3 experiments/shm-first-bundle/export_telemetry.py
```

Run the driver inside `script -q -e` to record the real terminal. Commands, output,
return codes, original CSVs, binary/library hashes and channel release evidence
are retained. The existing Kubernetes Prometheus/Grafana/DCGM deployment is
reused; the campaign exporter exposes progress and non-overlapping Worker and
launcher cgroup CPU. Screenshots are actual post-run Grafana/log inspections.

Formal settings are frozen in `protocol.json` before execution: 5 independent
repetitions per configuration; query, kernel launch+sync, and copy pairs at
4KiB/1MiB/16MiB. Each condition measures 10s after at least 3s/50 operations warmup.
This keeps the original microbenchmark measurement duration; it is a targeted
latency campaign, not the proposed later 60s workload sweep. Large-copy samples
are insufficient for a strong p99 claim; p99 is omitted below 10,000 samples.

The same serial workload and synchronization boundaries are maintained. This
does not measure API batching, Graphs, quota enforcement or transport-only
TCP/SHM effects. Native CUDA and the original Flyt TCP implementation are not
relabelled as matched controls. No failed run is silently counted as a success.
