"""Print compact tables from actual analysis output for terminal inspection."""
import json,sys
from pathlib import Path
s=json.loads((Path(sys.argv[1])/'analysis/summary.json').read_text())
mode=sys.argv[2]
if mode=='single':
 print('cap   n  GPU_%    jobs/s +/- SD     p95_ms    fixed_s   cap verdicts')
 for cap,r in s['single'].items():
  print(f"{cap:>3} {r['n']:3} {r['gpu_util_mean']:7.2f} {r['throughput']['mean']:8.2f} +/- {r['throughput']['sd']:5.2f} {r['p95_ms']['mean']:8.2f} {r['fixed_seconds']['mean']:10.2f} {','.join(r['enforcement'])}")
elif mode=='paths':
 print('metric / bytes              N(us)         T(us)         S(us)   n/path')
 for k,r in s['overhead'].items():
  if k.startswith(('resident','transfer')):continue
  print(f"{k:24} "+' '.join(f"{r[p]['mean_us']['mean']:13.2f}" for p in 'NTS')+f"   {r['N']['n']}")
 print('\nthroughput (jobs/s)          N             T             S')
 for k,r in s['overhead'].items():
  if k.startswith(('resident','transfer')):print(f"{k:24} "+' '.join(f"{r[p]['operations_per_s']['mean']:13.2f}" for p in 'NTS'))
elif mode=='shared':
 print('A/B/slot   n    solo_q   shared_q  retention  solo_p95 shared_p95')
 for k,r in s['shared'].items():print(f"{k:10} {r['n']:2} {r['solo_q']:9.2f} {r['shared_q']:9.2f} {r['retention']:9.3f} {r['solo_p95_ms']:9.2f} {r['shared_p95_ms']:10.2f}")
else:raise SystemExit('unknown table')
