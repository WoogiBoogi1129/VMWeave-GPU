import json
from pathlib import Path
O=Path('experiments/ai-passthrough/results/20261026-rodinia-steady');out=[]
for p in sorted((O/'diagnostic').glob('*/*/*/api-profile.json')):
 d=json.loads(p.read_text());r=json.loads((p.parent/'result.json').read_text());assert r['correct'] and r['returncode']==0
 groups={'allocation':['cudaMalloc','cudaFree'],'copy':['cudaMemcpy'],'launch':['cudaLaunchKernel'],'synchronization':['cudaDeviceSynchronize'],'events':['cudaEventCreate','cudaEventCreateWithFlags','cudaEventDestroy','cudaEventRecord','cudaEventSynchronize','cudaEventElapsedTime'],'other':['cudaGetLastError']}
 out.append({'mode':r['mode'],'workload':r['workload'],'scope':d['scope'],'invocations':3,'warmups_included':2,'initialization_included':True,'groups':{g:{'calls':sum(d['apis'][a]['calls'] for a in apis),'wall_s':sum(d['apis'][a]['wall_ns'] for a in apis)/1e9,'nonzero_returns':sum(d['apis'][a].get('nonzero_returns',0) for a in apis)} for g,apis in groups.items()},'apis':d['apis'],'memcpy_requested_bytes_by_kind':d['memcpy_requested_bytes_by_kind']})
assert len(out)==16,len(out)
(O/'diagnostic-summary.json').write_text(json.dumps(out,indent=2))
