"""Plain terminal inspection of the computed CSV; not a result dashboard."""
import csv,sys
from pathlib import Path
rows=list(csv.DictReader((Path(sys.argv[1])/'aggregate-summary.csv').open()));mode=sys.argv[2]
if mode=='cpu':
 print('CPU cost: nonoverlapping Pod cgroups; approximate window alignment')
 print(f'{"mode":12} {"path":4} {"active cores":>12} {"CPU us/work":>14}')
 for r in csv.DictReader((Path(sys.argv[1])/'cpu-summary.csv').open()):
  if r['mode'] in ['resident','transfer']:print(f'{r["mode"]:12} {r["path"]:4} {float(r["mean_active_cores"]):12.3f} {float(r["mean_cpu_microseconds_per_operation"]):14.3f}')
 print('Source: cpu-summary.csv; excludes shared control/monitoring services')
 raise SystemExit(0)
print('Independent session means (all valid repetitions)')
print('N = host CUDA + HAMi; T = Flyt TCP + MPS; S = proposed SHM + HAMi')
print()
print(f'{"metric / payload":32} {"path":4} {"mean":>11} {"SD":>10} {"n":>3}')
for r in rows:
 if (r['metric']=='throughput')!=(mode=='throughput'):continue
 name=(r['mode'] if mode=='throughput' else r['metric'])+(f' {int(r["bytes"])//1024}K' if r['mode']=='copy' else '')
 print(f'{name:32} {r["path"]:4} {float(r["mean"]):11.3f} {float(r["sample_sd"]):10.3f} {r["n_sessions"]:>3}')
print('\nUnits: '+('completed operations/s' if mode=='throughput' else 'microseconds'))
print('Source: aggregate-summary.csv -> per-session CSV -> raw *.csv.xz')
