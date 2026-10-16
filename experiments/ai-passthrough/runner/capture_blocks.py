"""Capture completed Grafana ranges; preserve actual URL, timestamp and image hash."""
import json,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];E=R/'results/20261016'
if '--equal-budget' in sys.argv:E=E/'equal-budget'
for p in sorted(E.glob('b*-*')):
 if not (p/'complete.json').exists():continue
 name=('equal-budget-' if E.name=='equal-budget' else '')+p.name
 image=R/'screenshots'/f'{name}.png'
 if image.exists():continue
 xs=[json.loads(f.read_text()) for f in p.glob('*/result.json')]
 start=int((min(x['start_utc'] for x in xs)-40)*1000)
 end=int((max(x['end_utc'] for x in xs)+15)*1000)
 url=f'http://localhost:13098/d/vmweave-ai-perf-20261016?orgId=1&from={start}&to={end}&var-run={name}&var-condition=.*&kiosk'
 (p/'screenshot-window.json').write_text(json.dumps({'from':start,'to':end,'url':url},indent=2)+'\n')
 subprocess.run(['node',str(R/'runner/capture.cjs'),url,str(image)],check=True)
 print(image,flush=True)
