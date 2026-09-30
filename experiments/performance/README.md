# VMWeave performance campaign (2026-09-30)

This campaign uses the current central `vmweave.io/v1alpha1` Operator. It does not
overwrite the September 28/29 measurements. The executable protocol and outcomes
are in `../evidence/results/2026-09-30-performance/`.

## Agreed scope

* HAMi compute 25/50/75/100 is an **SM utilization upper limit**, not reserved
  physical cores, guaranteed throughput, or a competition weight. Compute 100 is
  the baseline without compute throttling. Memory control remains enabled.
* N = host direct CUDA + HAMi; T = Flyt-based TCP/RPC + MPS; S = VMWeave SHM + HAMi.
  N/S use the same explicit FORCE policy. T uses all 188 physical SMs. This is a
  comparison of complete implementations, not an isolated TCP-versus-SHM effect.
* Separate two-VM steady-state experiments are removed. The concurrent interval
  of the start/stop experiment provides that observation. 100/100, fairness-index
  claims, and mixed-workload expansion are excluded from the mandatory campaign.
* Single VM: four caps, five fresh allocations per cap, warmup 30 s, timed window
  120 s with central 90 s aggregation, followed by a fixed number of identical
  jobs. Independent repetition is a fresh VM/Worker allocation.
* Two VMs: 50/50 and 25/75, both always-active roles, five repetitions. Both VMs
  boot and warm before the common start. A runs 240 s; B runs from +60 to +180 s.
  Compare A-alone (15–45 s), concurrent (90–150 s), and recovered (195–225 s).
  The complementary run provides each VM's same-cap solo baseline.
* N/T/S: five fresh sessions per path, seven conditions: query, launch+sync,
  H2D/D2H at 4 KiB/1 MiB/16 MiB, resident work, and transfer-inclusive work.
  Microbenchmarks use 10 s measurement, throughput 30 s; every condition warms
  for at least 10 s and 50 iterations. The three paths execute sequentially.

## Pilot and interpretation

Pilot observations are retained separately and never counted as formal repeats.
The GPU, runtime policy, mapped HAMi library, actual output verification, and
measurement visibility must be established before formal measurements. A
measured upper-limit violation is an experimental **failure of enforcement**,
not an invalid CUDA run and not a reason to discard unfavorable measurements.
If the policy is demonstrably active but inaccurate, the four-cap and shared
experiments characterize that limitation; they do not claim successful resource
isolation. If policy application/measurement cannot be established at all, the
dependent enforcement verdict remains NOT_EVALUATED.

The diagnostic candidate with 524288 internal iterations reached only about 77%
GPU utilization on S at cap 100. The 1048576-iteration candidate reached about
88%, so it is selected before formal measurements. Input is 2 MiB, grid 2048,
block 256, uint32 recurrence; every output element is checked after each window.
The fixed workload is selected from that pilot, not from formal outcomes.

Report both mean and time-series limit behavior. The research acceptance rule
is mean utilization <= cap + 10 percentage points over the central window, with
>=95% valid telemetry and verified nonzero work. This tolerance is an experiment
criterion, not a HAMi guarantee. GPU whole-device DCGM values support single-VM
evaluation only. Shared VM utilization uses the exact Worker Pod/GPU UUID HAMi
series (healthy exporter), cross-checked against Worker-PID pmon samples. Actual
pmon cadence is recorded and is not assumed to equal its requested interval.
The pre-shared-run clarification is in `utilization-attribution.json` in the results. Missing/unsupported telemetry is not zero. HAMi's cap-100 utilization series
may stay zero even during real GPU execution and must not be used as proof of idle.

## Execution and evidence

Prepare an idle GPU and approved profiles, fresh PVCs/VMs, a current Worker image,
matching guest shim, and the patched legacy Flyt baseline. `common.py` centralizes
the selected node/GPU/namespaces and records command, stdin, stdout, stderr,
timestamp and exit code. The checked-in scripts are specific to this recorded
testbed: review constants and provision images/SSH keys before reproducing.

`setup_monitoring.py` creates dedicated Prometheus 3.5.0/Grafana 12.0.2 Pods and a
one-second DCGM Exporter. Existing GPU Operator telemetry is left intact. Also
collect HAMi and node-exporter metrics, exact non-overlapping Pod cgroup CPU
counters, nvidia-smi process telemetry, and actual application progress. Keep
credentials and SSH private keys only under `.local/`.

```
bash experiments/performance/build.sh
python3 experiments/performance/setup_monitoring.py
python3 experiments/performance/setup_tcp.py
script -q -f -e -c 'python3 experiments/performance/run.py overhead' .local/performance-20260930/overhead.terminal
script -q -f -e -c 'python3 experiments/performance/run.py single' .local/performance-20260930/single.terminal
script -q -f -e -c 'python3 experiments/performance/run.py shared' .local/performance-20260930/shared.terminal
```

Record the real terminal session, including automatic execution. Capture actual
Grafana pages with absolute UTC windows after measurement to avoid browser load
inside timed windows. Label those captures post-run inspection. Export raw
Prometheus range responses, dashboard JSON and configuration, application sample
CSVs, runtime identities, source/binary hashes and normal Released evidence.
Use monotonic clocks for latency and measured guest-host clock offsets for
cross-machine event alignment. Do not synthesize command results or screenshots.

Preparation failures remain in the pilot evidence. Formal failures stop the
driver for diagnosis; no silent rerun or deletion. Resume only missing runs with
new names and an explicit deviation record. Drain owned channels by UID; do not
force finalizers or modify unrelated user resources.

After collection, `verify.py` independently checks exact sample counts, output,
clock continuity, shared start offsets (250 ms tolerance), B context lifetime,
and release identities. `analyze.py`, `plot.py`, and `report.py` regenerate the
tables/figures/report. `capture_grafana.cjs` and `capture_terminal.cjs` capture
real retained-data dashboards and real ttyd/tmux log inspection.
`cleanup.py` is gated on full verification and deletes only recorded resource
UIDs; it leaves the monitoring installation and data intact.
