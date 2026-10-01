# Monitoring and actual captures

The existing dedicated `vmweave-performance` Kubernetes deployment was reused:
Prometheus, Grafana, NVIDIA DCGM Exporter, HAMi metrics, and node-exporter.
The campaign exporter samples disjoint Pod cgroup CPU counters once per second:
T includes launcher, cell, and its isolated cluster manager/Mongo; S includes
launcher and Worker. QEMU and Guest execution are included in launcher CPU.
Common Kubernetes and monitoring services are outside those totals.

- Grafana dashboard UID: `vmweave-system-comparison`.
- Testbed Grafana: `http://10.98.3.238:3000`.
- Testbed Prometheus: `http://10.98.3.238:9090`.
- Original CPU samples: [cpu.jsonl](cpu.jsonl).
- Per-run Prometheus queries, absolute ranges and raw responses:
  `../runs/<run>/telemetry.json`.
- [Exporter source](../../../../system-comparison/exporter.py).

Device utilization is a whole-GPU signal, not per-VM utilization. GPU series
are matched by physical UUID; the exporter-visible GPU ordinal can differ from
the host ordinal. Prometheus 1-second query points can repeat a DCGM sample and
are not independent repetitions. Guest/Host clock offsets and uncertainty are
preserved in each run's identity file.

Microbenchmark latency comes from original Guest CSVs. This campaign does not
export per-API latency samples to Grafana. An empty `application_latency` query
is therefore expected, as is unavailable HAMi per-container utilization when
that path does not expose it. Neither is replaced with fabricated values.
Completed-operation counters restart between workloads; Grafana's rate near a
boundary is for visual context. Exact throughput uses each recorded interval's
completed count and elapsed time.

Grafana PNGs are actual post-run views of retained data at absolute UTC ranges.
Terminal PNGs show real ttyd/tmux log-inspection commands, with command exit
codes and pane text. Automated execution is not represented as human typing.
Original terminal transcripts are separately preserved in `../terminal`.

After collection, only the `system-comparison` scrape job and exporter are
removed. The monitoring deployment, historical data, and dashboard remain.
Service addresses require testbed access; raw data and captures remain portable
in the repository.
