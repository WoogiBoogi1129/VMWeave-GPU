"""Capture fixed historical intervals from the actual Grafana instance."""
import json,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;R=P/'results/20261016/runs';E=P/'evidence/20261016';ROOT=P.parents[1]
for label,names in [('single-1g',['vram-single-r5-1024']),('single-4g',['vram-single-r5-4096']),('pair',['vram-pair-v3-r1-ab-a','vram-pair-v3-r1-ab-b']),('pytorch',['vram-torch-r1-1024']),('trained-boundary',['vram-mlp-boundary-v2-r1-1024'])]:
 events=[]
 for n in names:
  file=R/n/('torch-events.jsonl' if 'torch' in n or 'mlp-boundary' in n else 'events.jsonl');events.extend(json.loads(l) for l in file.read_text().splitlines())
 start=int((min(x['host_utc'] for x in events)-10)*1000);end=int((max(json.loads((R/n/'cleanup.json').read_text())['utc'] for n in names)+10)*1000)
 subprocess.run(['node',str(P/'capture_grafana.cjs'),str(E/'grafana'/label),str(start),str(end),','.join(names)],cwd=ROOT,check=True)
subprocess.run(['node',str(P/'capture_terminal.cjs')],cwd=ROOT,check=True)
print('Actual Grafana and terminal screenshots captured')
