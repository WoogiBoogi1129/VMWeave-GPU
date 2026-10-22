import json,math,csv,hashlib,shutil,statistics,subprocess
from pathlib import Path
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
D=Path(__file__).resolve().parent;ROOT=D.parents[3];BASE=ROOT/'.local/math-cache-20261022';R=BASE/'results'
A=torch.load(R/'correctness-baseline/tensors.pt',map_location='cpu',weights_only=True);B=torch.load(R/'correctness-candidate/tensors.pt',map_location='cpu',weights_only=True)
for step in ['1','10','100']:
 assert torch.equal(A[step]['loss'],B[step]['loss'])
 for group in ['weights','gradients']:
  for n in A[step][group]:assert torch.equal(A[step][group][n],B[step][group][n])
(D/'correctness.json').write_text(json.dumps({'status':'PASS','steps':[1,10,100],'max_abs_error':0,'baseline_tensor_sha256':hashlib.sha256((R/'correctness-baseline/tensors.pt').read_bytes()).hexdigest(),'candidate_tensor_sha256':hashlib.sha256((R/'correctness-candidate/tensors.pt').read_bytes()).hexdigest()},indent=2))
def host_cpu(label,v):
 samples=[]
 for line in (R/label/'host-cpu.jsonl').read_text().splitlines():
  q=json.loads(line)
  if 'processes' in q and v['start_utc']<=q['utc']<=v['start_utc']+v['elapsed_seconds']:samples.append(q)
 if len(samples)<2:return None
 a,b=samples[0],samples[-1];key=lambda p:(p['pod_uid'],p['pid'],p['start_ticks']);first={key(p):p['cpu_seconds'] for p in a['processes']};last={key(p):p['cpu_seconds'] for p in b['processes']}
 return {'estimated_cores':sum(last[k]-first[k] for k in first.keys()&last.keys())/(b['utc']-a['utc']),'covered_seconds':b['utc']-a['utc'],'scope':'QEMU/Worker Pod process counters; common PID/start identities, interior samples'}
rows=[];pairs=[]
for b in range(1,4):
 group={}
 for variant in ['baseline','candidate','restored']:
  label=f'b{b}-{variant}';v=json.loads((R/label/'result.json').read_text());assert not v['profiled']
  group[variant]=v
  if variant=='candidate':
   assert v['math_cache_after'][0]==1
   assert v['math_cache_after'][1]-v['math_cache_before'][1]==1000
   assert v['math_cache_after'][2]-v['math_cache_before'][2]==0
  rows.append({'run':label,'samples_per_second':v['samples_per_second'],'elapsed_seconds':v['elapsed_seconds'],'guest_cpu_seconds':v['guest_cpu_seconds'],'voluntary_switches':v['context_switches']['voluntary'],'wire_requests':v['cache_after'][3]-v['cache_before'][3],'health_checks':v['cache_after'][4]-v['cache_before'][4],'sampled_pod_cores':(host_cpu(label,v) or {}).get('estimated_cores'),'cpu_sample_seconds':(host_cpu(label,v) or {}).get('covered_seconds')})
 pairs.append({'block':b,'candidate_over_baseline':group['candidate']['samples_per_second']/group['baseline']['samples_per_second'],'candidate_over_restored':group['candidate']['samples_per_second']/group['restored']['samples_per_second']})
with (D/'throughput.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
names={'0x1002':'device query (mostly cache hits)','0x2107':'primary context query (mostly cache hits)','0x2044':'CUDA kernel launch','0x3103':'BLAS GEMM','0x3104':'BLAS stream set','0x3105':'BLAS math set','0x3109':'BLAS workspace set','0x1020':'device synchronize'}
profiles={}
for label in ['profile-baseline','profile-candidate']:
 result=json.loads((R/label/'result.json').read_text());client=json.loads((R/label/'client-api-timing.json').read_text());broker=json.loads((R/label/'broker-api-timing.json').read_text());elapsed=result['elapsed_seconds'];apis=[]
 for api,a in client['apis'].items():
  server=broker['apis'].get(api,[0,0,0]);apis.append({'api':api,'name':names.get(api,api),'calls':a[0],'calls_per_step':a[0]/200,'caller_wall_seconds':a[1]/1e9,'caller_thread_cpu_seconds':a[2]/1e9,'caller_wall_percent':a[1]/1e9/elapsed*100,'broker_calls':server[0],'broker_exchange_seconds':server[1]/1e9,'broker_thread_cpu_seconds':server[2]/1e9})
 total=sum(a['caller_wall_seconds'] for a in apis);setters=sum(a['caller_wall_seconds'] for a in apis if a['api'] in ['0x3104','0x3105','0x3109'])
 profiles[label]={'elapsed_seconds':elapsed,'samples_per_second':result['samples_per_second'],'api_total_seconds':total,'outside_api_boundary_seconds':elapsed-total,'setters_seconds':setters,'setters_zero_cost_counterfactual_speedup':elapsed/(elapsed-setters),'apis':apis,'health':broker['apis'].get('0x7')}
 with (D/(label+'.csv')).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(apis[0]),lineterminator="\n");w.writeheader();w.writerows(apis)
means={v:statistics.mean(x['samples_per_second'] for x in rows if x['run'].endswith('-'+v)) for v in ['baseline','candidate','restored']}
summary={'status':'PASS','workload':'small/batch1024/resident/FP32','warmup_steps':30,'measured_steps':200,'means_samples_per_second':means,'paired_ratios':pairs,'geomean_candidate_over_baseline':math.exp(statistics.mean(math.log(x['candidate_over_baseline']) for x in pairs)),'geomean_candidate_over_restored':math.exp(statistics.mean(math.log(x['candidate_over_restored']) for x in pairs)),'profiles':profiles,'profile_throughput_ratio_to_unprofiled_mean':{v:profiles['profile-'+v]['samples_per_second']/means[v] for v in ['baseline','candidate']},'limitations':['One workload, one host, three sequential baseline/candidate/restored blocks; not an upper performance limit.','Nested caller/broker times must not be summed. Wall minus thread CPU includes blocking/descheduling; it is not isolated scheduler or GPU time.','Setter zero-cost counterfactual is accounting only; stream resets workspace and cannot be skipped independently.','The profiler state_cache=false field refers to its disabled diagnostic shim; real state cache is enabled in result cache_before/cache_after.','No new passthrough measurements.']}
summary['median_candidate_over_baseline']=statistics.median(x['candidate_over_baseline'] for x in pairs)
summary['limitations'].append('Block 1 candidate has unusually low elapsed AND Guest CPU time; all results retained. The cause is not isolated; do not generalize the geometric mean.')
(D/'summary.json').write_text(json.dumps(summary,indent=2))
fig,ax=plt.subplots(figsize=(7,4));colors=['#597a9a','#e29332','#8c9b9a'];xs=range(3)
for k,v in enumerate(['baseline','candidate','restored']):
 vals=[x['samples_per_second']/1000 for x in rows if x['run'].endswith('-'+v)];ax.scatter([k]*len(vals),vals,color=colors[k],zorder=3);ax.hlines(means[v]/1000,k-.2,k+.2,color=colors[k],linewidth=3)
ax.set_xticks(list(xs),['Baseline','Math-mode dedup','Restored']);ax.set_ylabel('Training throughput (thousand samples/s)');ax.set_title('State cache ON; 3 baseline/candidate/restored blocks');ax.grid(axis='y',alpha=.25);fig.tight_layout();fig.savefig(D/'throughput.png',dpi=170);plt.close(fig)
p=profiles['profile-baseline'];labels=[];values=[]
for a in p['apis']:
 if a['api'] in ['0x2044','0x3103','0x3104','0x3105','0x3109']:labels.append(a['name']);values.append(a['caller_wall_seconds']/200*1000)
labels+=['Other API calls','Outside API boundary'];values+=[(p['api_total_seconds']-sum(values)*.2)/.2,p['outside_api_boundary_seconds']/.2]
fig,ax=plt.subplots(figsize=(8,4));ax.barh(labels,values,color='#597a9a');ax.set_xlabel('Caller wall time (ms per training step)');ax.set_title('Measured baseline; nested broker time excluded');fig.tight_layout();fig.savefig(D/'decomposition.png',dpi=170);plt.close(fig)
print(json.dumps({k:v for k,v in summary.items() if k!='profiles'},indent=2))
