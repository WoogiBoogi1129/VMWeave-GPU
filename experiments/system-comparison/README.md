# TCP/RPC versus improved SHM: whole-system experiment

This campaign compares the existing Flyt TCP/RPC + MPS system with the improved
VMWeave SHM + HAMi system. It does not isolate the transport medium. HAMi quota
enforcement, fixed-arrival-rate/burst tests, application training/inference, and
multi-VM sharing are outside this campaign.

Both paths use the same GPU, 8-vCPU/16GiB Guest image, workload source, input
data, call order and explicit synchronization boundaries. T uses all 188
physical SMs verified through the current CUDA driver; S uses HAMi FORCE 100.
Both request 4096MiB of GPU memory. S retains the already validated runtime
binaries and defaults (zero active spin, short sleeps, optimized private copies).
Internal SHM metrics and detailed request tracing are off. T's existing startup
logging remains, with no per-request debug stream observed in the pilot.

The kernel PTX source is identical. S loads PTX through its normal runtime; T
uses the previously normalized offline cubin required by the legacy ELF parser.
This module-loading/compiler path difference is explicitly part of the systems,
not falsely represented as identical GPU machine code. Hashes and normalization
provenance are preserved. VM boot, CUDA setup, allocations, module loading and CSV
writing are outside each measured window.

Each of five matched repetitions contains a fresh T session and a fresh S
session, run sequentially. Pair order alternates; workload order is shuffled
with a frozen seed and is identical within each pair. Eight windows per session:
query, short launch+sync, long launch+sync (1,048,576 integer loop iterations),
and H2D/D2H copy pairs at 4KiB, 64KiB, 1MiB, 4MiB and 16MiB. Each window warms
for at least 10 seconds/50 operations, then measures 60 seconds. Copies report
direction-specific latency under an alternating H2D/D2H pattern. Latency uses
Guest monotonic time and includes completion synchronization. Output is checked
over the entire final buffer for every window; it is not checked after every
individual iteration.

CPU affinity: QEMU/Guest 0–7, SHM Worker or TCP cell 16–19; dedicated legacy
cluster manager/Mongo 20–23. CPU accounting adds disjoint Pod cgroups: S Worker
and launcher; T cell (RPC, MPS and node manager), launcher (Guest/client manager),
and cluster manager/Mongo. Common Kubernetes/monitoring infrastructure is outside
these totals and whole-host CPU is retained separately. The legacy manager is
removed after each T session, and each T starts a fresh manager/database.

## Execution and preservation

The isolated paths are `.local/system-comparison-20261001` (private binaries,
credentials and driver logs) and `experiments/evidence/results/2026-10-01-system-comparison`
(public evidence). Existing experiment bundles are immutable. Testbed-specific
node, GPU UUID, service addresses and image digests are explicit in the harness.
The Guest SSH key and legacy Mongo credentials must remain private.

1. Provision the recorded original TCP artifacts, current SHM artifacts and
   identical kernel modules into the private artifacts directory.
2. `build.py` rebuilds the common probe, disables Worker metrics through image
   configuration, imports exact images and retains stopped image references.
   These references prevent the node's existing image GC from evicting local-only
   images. They are never started and are removed after the campaign.
3. `setup_tcp.py` creates only the campaign's dedicated manager. `monitor.py`
   reuses Prometheus/Grafana/DCGM and adds one exporter job/dashboard.
4. Run `exporter.py`, then execute `run.py pilot-ready` in `script -q -e`.
   Review correctness, CPU capture, transport, runtime libraries, policies and
   long-kernel timing before freezing `protocol.json`.
5. Run `run.py formal` in a real terminal transcript. Measured failures are
   preserved, never silently overwritten. An incomplete attempt stops the driver.
6. Run `analyze.py`, `analyze_cpu.py`, `export_telemetry.py`, and `verify.py`.
   Completeness does not depend on which system wins. Report mean/SD across
   five sessions, p50/p95, and p99 only with at least 10,000 samples per run.
7. Produce actual post-run Grafana and terminal captures, report limitations and
   preparation failures, remove only UID-matched campaign resources, verify prior
   bundle integrity, and generate the new checksum manifest before publishing.

The initial preparation attempt encountered a removed Mongo image and a helper
network DNS mismatch; image retrieval used the host network without changing
global DNS. The first pilot stopped before workload execution because the old
affinity helper only matched QEMU/Worker, not manager processes. A dedicated
UID-restricted manager helper fixes that preparation step. Attempts and raw
command outputs are retained separately from the measured pilot and formal runs.
