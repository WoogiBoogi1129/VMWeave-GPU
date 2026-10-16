"""Publish selected non-secret runtime identity and reclamation evidence."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[3];B=ROOT/'.local/ai-passthrough-20261016/audit/runs';E=ROOT/'experiments/ai-passthrough/results/20261016/identities'
for source in B.iterdir():
 if not (source/'cleanup.json').exists():continue
 destination=E/source.name;destination.mkdir(parents=True,exist_ok=True)
 for name in ['identity.json','worker.json','vmi.json','library-mount.json','worker-libraries.json','channel-bound.json','channel-released.json','cleanup.json','clock-map.json','worker-output.txt']:
  if (source/name).is_file():shutil.copyfile(source/name,destination/name)
 for p in source.glob('*-affinity.json'):shutil.copyfile(p,destination/p.name)
print('Published completed session identities')
