"""Publish selected supplemental evidence; omit keys and cluster inventories."""
import pathlib,json,csv,hashlib,tarfile,shutil,datetime,statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=pathlib.Path(__file__).resolve().parents[3];exp=ROOT/'experiments/thesis-isolation';base=exp/'results/20261012-campaign';campaign=base/'expanded-full-20261013132650';analysis=campaign/'analysis';out=exp/'evidence/20261014-supplement';out.mkdir(parents=True,exist_ok=True)
files={base/name for name in json.loads((analysis/'source-sha256.json').read_text())}
files.update(analysis.glob('*'));files.update(campaign.glob('*.json'));activity=[];tz=datetime.timezone(datetime.timedelta(hours=9))
for r in json.loads((campaign/'protocol.json').read_text())['plan']:
 p=base/'pairs'/r['name'];files.add(p/'gpu-samples.csv');samples=[]
 for row in csv.DictReader((p/'gpu-samples.csv').open()):
  row={k.strip():v.strip() for k,v in row.items()};t=datetime.datetime.strptime(row['timestamp'],'%Y/%m/%d %H:%M:%S.%f').replace(tzinfo=tz).timestamp();samples.append((t,float(row['utilization.gpu [%]'].split()[0]),float(row['utilization.memory [%]'].split()[0])))
 for c in ['baseline','memory','compute']:
  ev=json.loads((p/(c+'-observer.json')).read_text());req=[x for x in ev if x['event']=='request'];assert all(x['latency_s']<40 for x in req)
  a=req[0]['received_host_utc'];z=ev[-1]['received_host_utc'];ss=[x for x in samples if a+1<=x[0]<=z-1];assert len(ss)>=1134
  activity.append({'trial':r['name'],'condition':c,'samples':len(ss),'gpu_mean_pct':statistics.mean(x[1] for x in ss),'memory_activity_mean_pct':statistics.mean(x[2] for x in ss)})
assert {(r['trial'],r['condition']):r for r in activity}=={(r['trial'],r['condition']):r for r in json.loads((campaign/'activity.json').read_text())}
# Calibration and pilot records, including the failed initial setup, are separate evidence.
patterns=['iso-load-cal-*','iso-load-wide-*','expanded-pair-*','iso-access-pilot-*','iso-absent-*','absent-sequence-*','supplement-summary-*']
for pattern in patterns:
 for d in base.glob(pattern):files.update(p for p in d.glob('*') if p.is_file() and p.suffix in ['.json','.csv'])
for d in (base/'pairs').glob('iso-wide-pilot-*'):files.update(p for p in d.glob('*') if p.is_file() and p.suffix in ['.json','.csv'])
for d in (base/'runs').glob('iso-absent-*'):
 for n in ['requests-events.jsonl','probe-stderr.txt','cleanup.json']:
  if (d/n).exists():files.add(d/n)
for d in (base/'runs').glob('iso-access-pilot-*'):
 for n in ['requests-events.jsonl','probe-stderr.txt','cleanup.json']:
  if (d/n).exists():files.add(d/n)
# Exclude any cluster identity snapshots from this public selection.
files={p for p in files if p.name not in ['target-pod.json','target-channel.json','observer-worker-after.json']}
with tarfile.open(out/'raw-evidence.tar.gz','w:gz') as tar:
 for p in sorted(files):tar.add(p,arcname=str(p.relative_to(base)),recursive=False)
(out/'raw-sha256.json').write_text(json.dumps({str(p.relative_to(base)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)},indent=2)+'\n')
for n in ['summary.json','per-run.csv','analysis.md']:shutil.copy(analysis/n,out/n)
shutil.copy(campaign/'activity.json',out/'activity.json')
old=json.loads((exp/'evidence/20261013/summary.json').read_text());new=json.loads((analysis/'summary.json').read_text())
comparison=[]
for label,s in [('original',old),('expanded',new)]:
 for g in s['groups']:
  if g['direction']=='all':comparison.append({'campaign':label,'condition':g['condition'],'throughput_rps':g['throughput_rps']['mean'],'p99_ms':g['p99_ms']['mean'],'throughput_drop_pct':100-g['throughput_retention_pct']['mean'],'p99_increase_pct':g['p99_increase_pct']['mean']})
(out/'comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
fig,axes=plt.subplots(1,2,figsize=(11,4))
for ax,key,title in zip(axes,['throughput_drop_pct','p99_increase_pct'],['Throughput decrease vs paired baseline (%)','p99 increase vs paired baseline (%)']):
 for i,c in enumerate(['memory','compute']):
  vals=[next(r[key] for r in comparison if r['campaign']==label and r['condition']==c) for label in ['original','expanded']]
  ax.bar([i-.18,i+.18],vals,width=.34,color=['#849db3','#195da8'])
 ax.set_xticks([0,1],['Memory load','Compute load']);ax.set_ylabel(title);ax.grid(axis='y',alpha=.2)
from matplotlib.patches import Patch
fig.legend(handles=[Patch(color='#849db3',label='Original load'),Patch(color='#195da8',label='Expanded load')],loc='upper center',ncol=2)
fig.suptitle('10 paired repetitions per campaign; descriptive comparison only',y=.01,fontsize=10);fig.tight_layout(rect=(0,.04,1,.9));fig.savefig(out/'comparison.png',dpi=180,bbox_inches='tight');fig.savefig(out/'comparison.pdf',bbox_inches='tight');plt.close(fig)
print(json.dumps(comparison,indent=2));print('ARCHIVE_BYTES',(out/'raw-evidence.tar.gz').stat().st_size)
