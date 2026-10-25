# Approved abbreviated three-way experiment

Comparators: Passthrough, Flyt SHM (pinned Guest/Host development branches), VMWeave v0.5.3. Official Rodinia 3.1 NW `2048 10` and LU `-s 2064`, seed 7. This is not an exact reproduction of the Flyt paper.

Gate: all three paths must build, execute via the intended transport, return correct full outputs and clean up. Small compatibility patches must be recorded; substantial feature work requires reporting before formal measurements. Never substitute Flyt TCP.

Use the same physical test GPU sequentially, matched VM CPU/RAM, identical source/input/compiler settings, single workload, VMWeave test quota 100%, sufficient common memory budget. Preserve production GPU and settings.

Three rounds: P/F/V, F/V/P, V/P/F. One preparation run per workload after each environment change excluded; each measured run is a new process. Two workloads per comparator per round: 18 measurements. Measure wall time from CUDA initialization/allocation through H2D, computation, D2H and completion synchronization. Exclude output-file writing and CPU validation. Report median/range, and P time / comparator time * 100. Three repetitions do not establish small statistical differences.

If more than 20% slower, CV above 10%, or consistently faster than P, diagnose the affected workload separately (copy/compute/synchronization, then call counts/waiting as needed). Stop on correctness or execution failures. Preserve failed samples.

Artifacts: manifest, build/compatibility evidence, reproduction commands, raw CSV/logs/correctness, comparison plot/report, cleanup evidence. Reuse existing VMWeave copy/deployment checks; no deployment or broad regression rerun.
