"""Re-render existing C3/C4 evidence; explicitly retain its 2026-09-24 date."""
import argparse,csv,datetime,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
here=Path(__file__).resolve().parent;source=here/'results/2026-09-24-showcase';out=a.output;out.mkdir(parents=True,exist_ok=True)
rows=list(csv.DictReader((source/'plots/samples.csv').open()))
for quota in [1024,4096]:
 data=[r for r in rows if r['run']==f'evidence-show-mem-{quota}-observe']
 origin=datetime.datetime.fromisoformat(data[0]['timestamp']).timestamp()
 x=[datetime.datetime.fromisoformat(r['timestamp']).timestamp()-origin for r in data]
 fig,ax=plt.subplots(figsize=(11,5),layout='constrained')
 for key,label in [('hami_container_memory_mib','HAMi accounting'),('gpu_process_memory_mib','Observed GPU process sum'),('gpu_memory_mib','Physical GPU memory')]:
  ax.plot(x,[float(r[key]) if r[key] else float('nan') for r in data],label=label)
 ax.axhline(quota,color='crimson',linestyle='--',label=f'Configured quota {quota} MiB')
 seen=set()
 for t,r in zip(x,data):
  if r['stage'] and r['stage'] not in seen:
   seen.add(r['stage']);ax.axvline(t,color='grey',alpha=.3);ax.text(t,.55*quota,r['stage'],rotation=90,fontsize=8)
 metrics=json.loads((source/f'runs/evidence-show-mem-{quota}-observe/run/metrics.json').read_text())
 oom=next(r for r in metrics['probe_results'] if r.get('stage')=='over_quota')
 ax.text(.02,.91,f"Additional request {oom['requested_bytes']:,} B -> CUDA OOM (2)\nOccurred before free; exact event timestamp was not logged",transform=ax.transAxes,fontsize=9)
 ax.set(title='Existing 2026-09-24 evidence — allocation / OOM / free / reallocation',xlabel='Seconds since first observed Ready snapshot',ylabel='MiB',ylim=(0,quota*1.13));ax.legend(loc='lower right');ax.grid(alpha=.2)
 fig.savefig(out/f'memory-{quota}.png',dpi=150);fig.savefig(out/f'memory-{quota}.svg');plt.close(fig)
agg=json.loads((source/'runs/evidence-show-aggregate/run/metrics.json').read_text())['probe_results'][0]
assert agg['cuda_status']==[0,2], 'Update session labels if the observed winner changes'
req=agg['request_per_process']/2**30
fig,ax=plt.subplots(figsize=(8,4),layout='constrained')
ax.bar(['Requested','Succeeded'],[req,req],label='Session A');ax.bar(['Requested','Succeeded'],[req,0],bottom=[req,req],label='Session B (OOM for allocation)');ax.axhline(4,color='crimson',linestyle='--',label='4 GiB aggregate quota')
ax.set(ylabel='GiB',title='Existing 2026-09-24 aggregate allocation evidence');ax.legend();fig.savefig(out/'aggregate.png',dpi=150);fig.savefig(out/'aggregate.svg');plt.close(fig)
comparisons=here/'results/2026-09-22-pytorch/comparisons'
table=[]
for f in sorted(comparisons.glob('pair-*.json')):
 d=json.loads(f.read_text());table.append({'case':f.stem,'tensor_checks':len(d['tensors']),'exceeded':sum(t['exceeded'] for t in d['tensors']),'max_absolute_error':max(t['max_absolute_error'] for t in d['tensors']),'max_relative_error':max(t['max_relative_error_nonzero_reference'] for t in d['tensors']),'status':d['status']})
with (out/'pytorch-correctness.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=table[0]);w.writeheader();w.writerows(table)
fig,ax=plt.subplots(figsize=(12,4),layout='constrained');ax.axis('off');ax.set_title('Existing 2026-09-22 PyTorch correctness — 8 cases, 144 tensor comparisons')
ax.table(cellText=[[r[k] for k in r] for r in table],colLabels=list(table[0]),loc='center',cellLoc='center');fig.savefig(out/'pytorch-correctness.png',dpi=160);plt.close(fig)
(out/'provenance.json').write_text(json.dumps({'scope':'Reanalysis only; not newly executed C3/C4','memory_source':str(source.relative_to(here)),'correctness_source':str(comparisons.relative_to(here)),'limitations':['OOM timestamp absent: textual annotation only','Aggregate after-free other-session retry not tested','Process sum is not per-VM in shared runs']},indent=2))
