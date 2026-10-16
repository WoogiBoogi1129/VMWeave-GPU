"""Flag internally inconsistent NVML clock reports without modifying raw samples."""
import csv,json
from pathlib import Path
E=Path(__file__).resolve().parents[1]/'results/20261016';rows=[];threshold=5000
for p in sorted(list(E.glob('b*-*/*/result.json'))+list(E.glob('equal-budget/b*-*/*/result.json'))):
 r=json.loads(p.read_text());bad=[]
 for sample in csv.DictReader((p.parent/'gpu.csv').open()):
  try:t=float(sample['utc']);clock=float(sample['clock_MHz'])
  except (ValueError,TypeError):continue
  if clock>threshold:bad.append({'utc':t,'reported_clock_MHz':clock,'within_measurement':r['start_utc']<=t<=r['end_utc']})
 if bad:rows.append({'run':str(p.parent.relative_to(E)),'samples':bad})
result={'screening_threshold_MHz':threshold,'observed_nvml_max_sm_MHz':2430,'screening_is_not_a_filter':True,'samples_above_threshold':sum(len(x['samples']) for x in rows),'samples_within_measurement':sum(q['within_measurement'] for x in rows for q in x['samples']),'runs':rows}
(E/'nvml-clock-observations.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k!='runs'})
