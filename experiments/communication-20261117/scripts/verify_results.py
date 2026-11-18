"""Independent standard-library checks of final counts, rates, quantiles and CIs."""
import array,csv,gzip,json,math,statistics,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1]
rows=list(csv.DictReader((P/'analysis/blocks.csv').open()))
assert len(rows)==320
seen=set();checked=0
for r in rows:
 key=(int(r['block']),r['mode'],int(r['id']));assert key not in seen;seen.add(key)
 s=P/'results'/f'b{key[0]}-{key[1]}'
 e=json.loads((s/'execution.json').read_text());m=next(x for x in e['results'] if x['id']==key[2])
 assert e['status']=='passed' and len(e['results'])==16
 raw=array.array('Q')
 with gzip.open(s/f'c{key[2]:02d}.u64.gz','rb') as f:raw.frombytes(f.read())
 if sys.byteorder!='little':raw.byteswap()
 n=len(raw);assert n==int(r['samples'])==m['completed'] and min(raw)>0
 assert m['elapsed_ns']>=30_000_000_000 and sum(raw)<=m['elapsed_ns']
 raw=sorted(raw)
 def quantile(p):
  k=(n-1)*p;lo=int(k);hi=min(lo+1,n-1);return (raw[lo]+(raw[hi]-raw[lo])*(k-lo))/1000
 assert math.isclose(float(r['p50_us']),quantile(.5),rel_tol=1e-10,abs_tol=1e-9)
 if n<1000:assert r['p95_us']==''
 else:assert math.isclose(float(r['p95_us']),quantile(.95),rel_tol=1e-10,abs_tol=1e-9)
 elapsed=m['elapsed_ns']/1e9
 if m['direction']=='kernel':assert math.isclose(float(r['kernels_s']),n*m['K']/elapsed,rel_tol=1e-12)
 else:assert math.isclose(float(r['GiB_s']),n*m['bytes']/elapsed/2**30,rel_tol=1e-12)
 assert (P/'evidence'/f'b{key[0]}-{key[1]}-released.json').exists()
 checked+=n
lookup={(int(r['block']),r['mode'],int(r['id'])):r for r in rows}
for r in csv.DictReader((P/'analysis/paired-ratios.csv').open()):
 id=int(r['id']);den=r['comparison'][-1];metric=r['metric']
 logs=[math.log(float(lookup[b,'V',id][metric])/float(lookup[b,den,id][metric])) for b in range(1,6)]
 mean=statistics.mean(logs);half=2.7764451051977987*statistics.stdev(logs)/math.sqrt(5)
 for key,v in zip(['ratio','low95','high95'],[mean,mean-half,mean+half]):assert math.isclose(float(r[key]),math.exp(v),rel_tol=1e-10)
quality=[]
for s in sorted((P/'results').glob('b[1-5]-[NVFL]')):
 obs=[json.loads(l) for l in (s/'observer.jsonl').read_text().splitlines()]
 foreign=[p for x in obs for p in x.get('target_processes',[]) if not p['owned']]
 thermal=[]
 for x in obs:
  if 'gpu' in x:
   try:
    reason=int(x['gpu'].split(',')[-1].strip(),16)
    if reason & (8|32|64|128):thermal.append(x)
   except ValueError:pass
 quality.append({'session':s.name,'observer_samples':len(obs),'foreign_gpu_processes':foreign,'hardware_or_thermal_slowdown_samples':len(thermal),'gpu_query_errors':sum('gpu_error' in x for x in obs)})
 assert not foreign and not thermal,s.name
out={'passed':True,'intervals':len(rows),'latency_samples_checked':checked,'independent_implementation':'Python standard library array/sort/statistics; no analyzer import','checks':['unique 5x4x16 matrix','raw count, positive time and elapsed >=30s','completed payload/kernel rate denominator','p50 and p95 gating/interpolation','paired log-ratio block t confidence intervals','session release evidence','GPU1 process ownership and hardware/thermal slowdown flags'],'quality':quality}
(P/'analysis/independent-verification.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='quality'},indent=2))
