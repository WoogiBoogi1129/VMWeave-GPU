# Monitoring and actual captures

The existing dedicated `vmweave-performance` Kubernetes deployment was reused:
Prometheus, Grafana, NVIDIA DCGM Exporter, HAMi metrics, and node-exporter.
The additional campaign exporter sampled non-overlapping Worker and launcher
Pod cgroup CPU counters once per second; the launcher includes QEMU/Guest CPU.
Its source is [exporter.py](../../../../shm-first-bundle/exporter.py).

- Grafana dashboard UID: `vmweave-shm-first` (provisioning JSON in this directory).
- In-cluster/testbed Grafana: `http://10.98.3.238:3000`.
- In-cluster/testbed Prometheus: `http://10.98.3.238:9090`.
- Original CPU samples: `cpu.jsonl`.
- Per-run Prometheus queries, absolute ranges and raw responses:
  `../runs/<run>/telemetry.json`.

Device utilization is a whole-GPU signal, not per-VM utilization. Detailed
microbenchmark API latency comes from the original Guest CSVs. The workload
exporter's last-operation latency is available for the shared load probe; it is
not substituted for unavailable per-API microbenchmark samples on Grafana.
Guest/Host offsets and alignment uncertainty are retained per run.

The Grafana PNGs are real post-run views of retained observations at absolute UTC
ranges. The terminal PNGs show actual log-inspection commands in ttyd/tmux, with
command exit codes and captured pane text. They are not simulated manual work.
Original automated terminal transcripts are separately retained in `../terminal`.

After collection, only the `shm-first` scrape job and its temporary exporter are
removed. The monitoring deployment, historical data and dashboard remain.
These service addresses require access to the testbed; the repository preserves
portable raw data and captures independently of that access.
