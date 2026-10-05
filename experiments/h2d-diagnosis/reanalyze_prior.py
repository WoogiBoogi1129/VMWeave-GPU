from common import *
import gzip,csv,statistics,hashlib
prior=ROOT/'experiments/evidence/results/2026-10-01-system-comparison'
rows=[]
for p in sorted((prior/'runs').glob('sc-r*-*/*copy-16777216.csv.gz')):
 with gzip.open(p,'rt') as f:a=list(csv.DictReader(f))
 x=[float(r['first_seconds'])*1000 for r in a];y=[float(r['second_seconds'])*1000 for r in a]
 sx=sorted(x);rows.append({'run':p.parent.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'count':len(x),'h2d_mean_ms':statistics.mean(x),'h2d_median_ms':statistics.median(x),'h2d_p95_ms':sx[int(.95*(len(x)-1))],'d2h_mean_ms':statistics.mean(y),'first_quarter_mean_ms':statistics.mean(x[:len(x)//4]),'last_quarter_mean_ms':statistics.mean(x[-len(x)//4:])})
pairs=[]
for i in range(1,6):
 t=next(r for r in rows if r['run']==f'sc-r{i}-t');s=next(r for r in rows if r['run']==f'sc-r{i}-s');pairs.append({'repeat':i,'delta_ms':s['h2d_mean_ms']-t['h2d_mean_ms'],'slowdown_pct':100*(s['h2d_mean_ms']/t['h2d_mean_ms']-1)})
save(OUT/'prior-analysis.json',{'rows':rows,'pairs':pairs,'limitation':'Original first_seconds includes H2D copy AND explicit sync; raw CSV cannot separate these.'})
print(json.dumps(pairs,indent=2))
