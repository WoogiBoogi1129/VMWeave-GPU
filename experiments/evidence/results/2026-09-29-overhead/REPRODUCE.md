# Reproduction contract

The exact protocol is `protocol.json`; the frozen measurement entry point is `source/run_overhead.py`.
This publication is a user-requested cutoff snapshot. The basic three repetitions
are complete, but the planned six-repetition extension is incomplete; see
`publication-cutoff.json` and `additional-native/README.md`.
This directory is a campaign snapshot, not a general deployment installer.
Use an idle GPU with UUID recorded in the protocol, the existing evidence
controller/hook and guest image, and two released evidence PVCs. Do not reuse
an allocation that has not reached `Released`.

1. Build `overhead_probe.c` three times with CUDA 12.8.1 headers: N links CUDA
   runtime/driver; T links `cricket-client.so`; S defines `FLYT_GUEST` and links
   `libflyt_guest.so`. All variants use `-O2` and the same operation source. Completion uses
   `cudaDeviceSynchronize` on all paths, since legacy `cuCtxSynchronize` is a
   local fallback and not a supported RPC synchronization call.
2. Copy `overhead_work.ptx` for N/S. Run `ptxas -arch=sm_120` for T, then run
   `normalize_overhead_cubin.py` to move the ELF section table to EOF. The
   normalization manifest proves that kernel and segment bytes are unchanged.
   This avoids the legacy loader's truncated length calculation. It happens
   before all timing, and is not an optimization of a measured operation.
3. Derive the performance Worker from the Stage 2 Worker, setting
   `FLYT_TRACE_REQUESTS=0` and `GPU_CORE_UTILIZATION_POLICY=DISABLE`. Keep HAMi
   injection and the 4096 MiB limit. Verify the running process environment,
   mapped libraries and SHA-256 values, not only the requested Pod spec.
4. T uses baseline commit `596a86939bae125d127a9ed6f70d92c332f47644`, the actual
   builder diff in `source/legacy-applied.patch`, and the repository's three
   existing compatibility patches: `flyt-module-resource-handle.patch`,
   `flyt-driver-launch-function-map.patch`, `flyt-driver-launch-stream-map.patch`.
   These repair invalid module/function handles and default-stream mapping.
   Label this path **Flyt-based TCP + MPS**, not an unmodified paper binary.
5. Deploy only campaign-owned Flyt manager/Mongo, GPU Cell and guest resources.
   The plain TCP VM uses namespace `flyt-overhead-tcp`; the SHM namespace
   requires a channel binding. Use the full qualified CDI GPU selector recorded
   in `overhead_tcp.py`. T receives 188 physical SMs and 4096 MiB. An isolated
   manager is recreated for each T session because the old manager retains
   disconnected GPU inventories. SSH keys and database credentials stay in
   `.local/overhead-20260929`; never publish them.
6. Start `overhead_cpu.py`, `overhead_monitor.py`, upstream Prometheus 3.5.0 and
   Grafana 12.0.2 using the captured monitoring configuration. Sampling is 1 s.
   GPU utilization is whole-device utilization. CPU samples are nonoverlapping
   parent Pod cgroups; never add guest CPU to the QEMU/launcher total again.
7. Run the campaign sequentially:

   ```sh
   PYTHONPATH=experiments/evidence python3 experiments/evidence/results/2026-09-29-overhead/source/run_overhead.py \
     --base .local/overhead-20260929 \
     --output experiments/evidence/results/2026-09-29-overhead
   ```

   Use a new output directory and fresh resource names for a new campaign; do not rerun into this published snapshot. The output directory must not already contain the selected session folders.
   Each path has three fresh sessions. Session order is N/T/S, T/S/N, S/N/T.
   Each session runs five 30 s microbenchmark windows and two 60 s throughput
   windows. Each window has at least 10 s and 50 full-operation warmup cycles.
   The program stays alive across conditions; exiting closes its SHM session.
8. This execution additionally records one protocol deviation in `exclusions.json`.
   A premature browser preview overlapped the first S query window. Preserve
   those samples but replace the whole first N/T/S query block with fresh
   `--repetitions 7 --condition-mask 1` sessions. These are logical repetition 1
   for query only; other conditions retain their original repetition 1.
   Complete this replacement before applying the variance extension rule.

9. Recompute validation and statistics from all original compressed CSV files (`.csv.xz` after lossless publication packing):

   ```sh
   .local/evidence-venv/bin/python experiments/evidence/results/2026-09-29-overhead/analysis-source/analyze_overhead.py \
     experiments/evidence/results/2026-09-29-overhead \
     --cpu .local/overhead-20260929/cpu.jsonl --plots
   ```

   If the frozen variation rule triggers, use `extension-decision.json`'s bit
   mask with `--repetitions 4,5,6 --condition-mask MASK` for all three paths.
   The mask selects query, kernel, copy 4 KiB, copy 256 KiB, copy 4 MiB,
   resident, transfer in bits 0 through 6. Keep the original valid samples.
10. Export Prometheus query ranges and Grafana dashboard JSON, then capture the
   actual Grafana page and actual ttyd/tmux terminal log inspection. Record
   absolute UTC windows. Screenshots taken after execution must be labeled
   post-run inspection. No recording is needed.
11. Drain owned SHM channels to `Released`, halt owned TCP VMs, UID-check and
    remove owned GPU Cells/manager/image-retention Pods, and stop only recorded
    monitoring PIDs. Preserve the unrelated baseline VM and user worktree edits.

Raw latency columns: query `first_seconds` = API return; kernel first = launch
return, second = launch through synchronization completion; copy first = H2D
and synchronization, second = D2H and synchronization. Throughput counts full
completed operations divided by actual window time. Setup, allocation, module
loading, output checking, CSV writing and cleanup are outside timed windows.

CUDA allocations use pageable host buffers. Full integer output is checked
once after each window and preserved. This does not claim per-iteration output
verification. Repetitions are independent sessions, not individual calls.

## Recompute the published bundle offline

`source/` preserves the files frozen before measurement. Publication packing,
exclusion accounting, independent verification and plotting evolved afterwards;
`analysis-source/` preserves the exact final postprocessing scripts and their
hash manifest. The measured probe/runtime sources and binaries remain checked
against `protocol.json`; do not replace the frozen snapshot with later scripts.

Use Python 3.12 with the versions in `analysis-environment.json`. To reproduce
CPU accounting from the public bundle, decompress `monitoring/cpu.jsonl.gz`
into a temporary file and pass it with `--cpu`. The analyzer reads the published
XZ samples directly. Run `analysis-source/verify_overhead.py` afterwards. First also recompute the `additional-native` directory with the same analyzer and CPU file. The verifier explicitly reports `campaign_complete: false` for this snapshot. Restore the actual
monitoring history with the procedure in `monitoring/README.md`.
