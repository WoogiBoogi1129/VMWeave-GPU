#!/usr/bin/env python3
"""Offline analysis: paired block ratios; no cluster access or private dependencies."""
import argparse,csv,json,math,random,statistics,hashlib
from pathlib import Path
MODES=['passthrough','flyt','vmweave']

def interval(ratios):
 assert len(ratios)>=2 and all(x>0 for x in ratios)
 logs=[math.log(x) for x in ratios];rng=random.Random(20261102)
 draws=sorted(math.exp(statistics.mean(rng.choices(logs,k=len(logs)))) for _ in range(10000))
 return {'geomean':math.exp(statistics.mean(logs)),'ci95':[draws[249],draws[9749]],'n_blocks':len(logs),'values':ratios}

def difference_interval(values):
 assert len(values)>=2 and all(math.isfinite(x) for x in values)
 rng=random.Random(20261102)
 draws=sorted(statistics.mean(rng.choices(values,k=len(values))) for _ in range(10000))
 return {'mean':statistics.mean(values),'ci95':[draws[249],draws[9749]],'n_blocks':len(values),'values':values}

def cpu_cost(directory,result):
 p=directory/'cpu.jsonl'
 if not p.exists():return None
 samples=[json.loads(l) for l in p.read_text().splitlines() if l]
 clocks=json.loads((directory/'clock.json').read_text());clock=min(clocks,key=lambda x:x['uncertainty'])
 lo=result['start_utc']-clock['offset'];hi=result['end_utc']-clock['offset']
 # Conservative inner window: avoids counting initialization and post-measurement validation.
 inside=[x for x in samples if lo+clock['uncertainty']<=x['utc']<=hi-clock['uncertainty']]
 if len(inside)<2:return None
 first,last=inside[0],inside[-1];duration=last['utc']-first['utc'];costs={}
 for name in sorted(first['pods'].keys() & last['pods'].keys()):
  usage=(last['pods'][name]['cpu']['usage_usec']-first['pods'][name]['cpu']['usage_usec'])/1e6
  costs[name]=usage
 return {'observed_seconds':duration,'fraction_of_timed_interval':duration/result['elapsed_seconds'],'cpu_seconds':sum(costs.values()),'mean_cores':sum(costs.values())/duration,'pods':costs,'cpu_seconds_per_step_estimate':sum(costs.values())/duration*result['step_seconds'],'clock_uncertainty_seconds':clock['uncertainty']}

def gpu_activity(directory,result):
 p=directory/'gpu.jsonl'
 if not p.exists():return None
 clocks=json.loads((directory/'clock.json').read_text())
 clock=min(clocks,key=lambda x:x['uncertainty'])
 lo=result['start_utc']-clock['offset']+clock['uncertainty']
 hi=result['end_utc']-clock['offset']-clock['uncertainty']
 rows=[]
 for line in p.read_text().splitlines():
  x=json.loads(line)
  if x.get('returncode')!=0 or not lo<=x['utc']<=x['end_utc']<=hi:continue
  fields=[v.strip() for v in x['csv'].split(',')]
  try:rows.append([float(v) for v in fields[1:]])
  except ValueError:continue
 if not rows:return None
 names=['utilization_percent','memory_mib','sm_clock_mhz','power_watts','temperature_c']
 return {'samples':len(rows),'metrics':{name:{'median':statistics.median(r[i] for r in rows),'min':min(r[i] for r in rows),'max':max(r[i] for r in rows)} for i,name in enumerate(names)}}

def analyze(root):
 protocol=json.loads((root/'protocol.json').read_text());expected=protocol['formal_blocks']
 data={};rows=[];resources={};command_ends=[]
 for p in sorted((root/'formal').glob('*/*/*/result.json')):
  block=p.parents[2].name;mode=p.parents[1].name;case=p.parent.name
  x=json.loads(p.read_text());assert x['completed'] and not x['correctness']
  assert x['steps']==protocol['steps'][case] and x['sync']==protocol['sync']
  key=(block,mode,case);assert key not in data;data[key]=x
  exit_info=json.loads((p.parent/'exit.json').read_text())
  command_ends.append(exit_info['end_utc'])
  command_wall=exit_info['end_utc']-exit_info['start_utc']
  cpu=cpu_cost(p.parent,x)
  resources['/'.join(key)]={'cpu':cpu,'gpu':gpu_activity(p.parent,x)}
  rows.append({'block':block,'mode':mode,'case':case,'steps':x['steps'],'batch':x['batch'],'seconds':x['elapsed_seconds'],'command_wall_seconds':command_wall,'samples_per_second':x['samples_per_second'],'step_ms':x['step_seconds']*1000,'guest_cpu_seconds':x['guest_cpu_seconds'],'observed_total_cpu_cores':cpu['mean_cores'] if cpu else '', 'cpu_window_fraction':cpu['fraction_of_timed_interval'] if cpu else '', 'total_cpu_seconds_per_step_estimate':cpu['cpu_seconds_per_step_estimate'] if cpu else '', 'h2d_bytes_per_step':x['h2d_bytes_per_step'],'d2h_bytes_per_step':x['d2h_bytes_per_step'],'final_loss':x['final_loss']})
 assert len(rows)==expected*3*len(protocol['steps']),(len(rows),expected)
 assert len({x['source_sha256'] for x in data.values()})==1
 cases={}
 for case in protocol['steps']:
  values=[x for (b,m,c),x in data.items() if c==case]
  assert len({x['fixture_sha256'] for x in values})==1
  assert len({(x['torch'],x['cuda']) for x in values})==1
  ref=data[('b1','passthrough',case)]['final_loss']
  assert all(math.isclose(x['final_loss'],ref,rel_tol=1e-4,abs_tol=1e-6) for x in values),case
  per={}
  for mode in MODES:
   values=[data[('b'+str(i),mode,case)] for i in range(1,expected+1)]
   per[mode]={'median_samples_per_second':statistics.median(x['samples_per_second'] for x in values),'median_step_ms':statistics.median(x['step_seconds']*1000 for x in values),'seconds_range':[min(x['elapsed_seconds'] for x in values),max(x['elapsed_seconds'] for x in values)]}
  ratios={}
  for baseline in ['passthrough','flyt']:
   ratios[baseline]=interval([data[('b'+str(i),'vmweave',case)]['samples_per_second']/data[('b'+str(i),baseline,case)]['samples_per_second'] for i in range(1,expected+1)])
  cases[case]={'systems':per,'vmweave_throughput_ratio':ratios}
 transfers={}
 for model in ['small','large']:
  for batch in [32,1024]:
   for mode in MODES:
    key=f'{model}-{batch}-{mode}'
    transfers[key]={'h2d_over_resident_time':interval([data[(f'b{i}',mode,f'{model}-{batch}-h2d')]['step_seconds']/data[(f'b{i}',mode,f'{model}-{batch}-resident')]['step_seconds'] for i in range(1,expected+1)])}
    transfers[key]['h2d_minus_resident_ms']=difference_interval([1000*(data[(f'b{i}',mode,f'{model}-{batch}-h2d')]['step_seconds']-data[(f'b{i}',mode,f'{model}-{batch}-resident')]['step_seconds']) for i in range(1,expected+1)])
    if batch==1024:
     transfers[key]['roundtrip_over_h2d_time']=interval([data[(f'b{i}',mode,f'{model}-{batch}-roundtrip')]['step_seconds']/data[(f'b{i}',mode,f'{model}-{batch}-h2d')]['step_seconds'] for i in range(1,expected+1)])
     transfers[key]['roundtrip_minus_h2d_ms']=difference_interval([1000*(data[(f'b{i}',mode,f'{model}-{batch}-roundtrip')]['step_seconds']-data[(f'b{i}',mode,f'{model}-{batch}-h2d')]['step_seconds']) for i in range(1,expected+1)])
 with (root/'measurements.csv').open('w') as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
 result={'formal_runs':len(rows),'blocks':expected,'cases':cases,'transfer_effects':transfers,'statistic':'Primary: paired block log-ratio geometric mean. Supplementary: paired step-time difference arithmetic mean (ms). Both use10000 block bootstrap draws, seed20261102, pointwise percentile95% intervals. No equivalence test or multiple-comparison adjustment.'}
 (root/'resource-summary.json').write_text(json.dumps(resources,indent=2)+'\n')
 if (root/'external-pods.jsonl').exists():
  from external_changes import summarize
  external=summarize(root/'external-pods.jsonl',protocol['created_utc'],max(command_ends))
  (root/'external-summary.json').write_text(json.dumps(external,indent=2)+'\n')
 (root/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
 return result

def plot(root,result):
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 colors={'passthrough':'#486b8c','flyt':'#c07d33','vmweave':'#268577'}
 fig,axs=plt.subplots(2,2,figsize=(12,8))
 for ax,(model,inp) in zip(axs.flat,[(m,i) for m in ['small','large'] for i in ['resident','h2d']]):
  for j,mode in enumerate(MODES):
   ys=[result['cases'][f'{model}-{b}-{inp}']['systems'][mode]['median_samples_per_second'] for b in [32,1024]]
   ax.bar([i+(j-1)*.24 for i in range(2)],ys,width=.23,color=colors[mode],label=mode)
  ax.set_xticks([0,1],['batch32','batch1024']);ax.set_yscale('log');ax.set_title(model+' / '+inp);ax.set_ylabel('samples/s (log scale)');ax.legend()
 fig.tight_layout();fig.savefig(root/'throughput.png',dpi=180);fig.savefig(root/'throughput.pdf');plt.close(fig)
 names=list(result['cases']);fig,ax=plt.subplots(figsize=(11,6))
 for j,baseline in enumerate(['passthrough','flyt']):
  vals=[result['cases'][c]['vmweave_throughput_ratio'][baseline] for c in names]
  ys=[x['geomean'] for x in vals];xs=[i+(j-.5)*.15 for i in range(len(names))]
  ax.errorbar(xs,ys,yerr=[[y-x['ci95'][0] for x,y in zip(vals,ys)],[x['ci95'][1]-y for x,y in zip(vals,ys)]],fmt='o',capsize=3,label='VMWeave / '+baseline)
 ax.axhline(1,color='gray',linestyle='--');ax.set_yscale('log');ax.set_xticks(range(len(names)),names,rotation=50,ha='right');ax.set_ylabel('Throughput ratio (higher is better)');ax.legend();fig.tight_layout();fig.savefig(root/'ratios.png',dpi=180);fig.savefig(root/'ratios.pdf');plt.close(fig)
 fig,axs=plt.subplots(2,2,figsize=(12,9))
 panels=[(axs[0,0],'h2d_over_resident_time','geomean',1,[f'{m}-{b}' for m in ['small','large'] for b in [32,1024]]),(axs[0,1],'roundtrip_over_h2d_time','geomean',1,[f'{m}-1024' for m in ['small','large']]),(axs[1,0],'h2d_minus_resident_ms','mean',0,[f'{m}-{b}' for m in ['small','large'] for b in [32,1024]]),(axs[1,1],'roundtrip_minus_h2d_ms','mean',0,[f'{m}-1024' for m in ['small','large']])]
 for ax,metric,estimate,reference,groups in panels:
  for j,mode in enumerate(MODES):
   vals=[result['transfer_effects'][g+'-'+mode][metric] for g in groups]
   ys=[v[estimate] for v in vals]
   ax.errorbar([i+(j-1)*.16 for i in range(len(groups))],ys,yerr=[[y-v['ci95'][0] for v,y in zip(vals,ys)],[v['ci95'][1]-y for v,y in zip(vals,ys)]],fmt='o',capsize=3,color=colors[mode],label=mode)
  ax.axhline(reference,color='gray',linestyle='--');ax.set_xticks(range(len(groups)),groups,rotation=25);ax.set_title(metric.replace('_',' '));ax.set_ylabel(('Step time ratio' if estimate=='geomean' else 'Step time difference (ms)')+' / 95% paired CI');ax.legend()
 fig.tight_layout();fig.savefig(root/'transfer-effects.png',dpi=180);fig.savefig(root/'transfer-effects.pdf');plt.close(fig)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).parent/'results/20261102');p.add_argument('--plots',action='store_true');a=p.parse_args()
 r=analyze(a.root)
 if a.plots:plot(a.root,r)
 print(json.dumps({'formal_runs':r['formal_runs'],'blocks':r['blocks']}))
