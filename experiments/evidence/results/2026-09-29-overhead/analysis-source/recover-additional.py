from pathlib import Path
import gzip,hashlib,json,shutil,time
b=Path('.local/overhead-20260929');o=Path('experiments/evidence/results/2026-09-29-overhead/additional-native/r4-N');src=b/'runs/evidence-perf-4-n/samples';manifest=[]
for f in sorted(src.iterdir()):
 target=o/(f.name+'.gz') if f.suffix=='.csv' else o/f.name
 old={'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()} if target.exists() else None
 if f.suffix=='.csv':
  with f.open('rb') as inp,gzip.open(target,'wb',compresslevel=1) as out:shutil.copyfileobj(inp,out)
 else:shutil.copy2(f,target)
 with f.open('rb') as inp:digest=hashlib.file_digest(inp,'sha256').hexdigest()
 manifest.append({'file':f.name,'raw_bytes':f.stat().st_size,'raw_sha256':digest,'previous_partial_export':old})
(o/'export-recovery.json').write_text(json.dumps({'utc':time.time(),'reason':'User cutoff interrupted publication gzip compression after all six measured windows completed. Re-export from intact original raw samples; no rerun or sample modification.','files':manifest},indent=2)+'\n')
print('Recovered',len(manifest),'raw files')
