"""Concise read-only progress, excluding exploratory pilot runs."""
import json
from common import OUT,BASE
runs=list((OUT/'runs').iterdir())
counts={key:sum(p.name.startswith('perf-'+key+'-') and (p/'cleanup.json').exists() and not (p/'failure.json').exists() for p in runs) for key in ['o','c','d']}
active=[p for p in runs if p.name.startswith('perf-') and not (p/'cleanup.json').exists()]
failures=[{'run':p.name,**json.loads((p/'failure.json').read_text())} for p in runs if p.name.startswith('perf-') and (p/'failure.json').exists()]
latest={}
for p in active:
 f=p/'stdout.jsonl'
 latest[p.name]=f.read_text().splitlines()[-1] if f.exists() and f.stat().st_size else 'preparing fresh resources'
print(json.dumps({'completed':counts,'expected':{'o':15,'c':20,'d':40},'active':latest,'failures':failures,'all_stages_complete':(OUT/'campaign-execution-complete.json').exists(),'continuation_error':(BASE/'continuation.txt').read_text()[-1200:] if (BASE/'continuation.txt').exists() else ''},ensure_ascii=False))
