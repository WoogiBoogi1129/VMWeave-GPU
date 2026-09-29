"""Cross-check the completed campaign: identities, policies, samples and order."""
import argparse,csv,hashlib,json,re,statistics
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();o=a.output
protocol=json.loads((o/'protocol.json').read_text());validation=json.loads((o/'validation.json').read_text());decision=json.loads((o/'extension-decision.json').read_text());windows=list(csv.DictReader((o/'window-summary.csv').open()));checks={};errors=[]
def check(name,condition):
 checks[name]=bool(condition)
 if not condition:errors.append(name)
check('all_output_elements_and_sample_counts',validation['status']=='PASS' and all(x['valid'] for x in validation['details']))
mask=decision['condition_mask'];planned=63+9*mask.bit_count();snapshot=(o/'publication-cutoff.json').exists();expected=63 if snapshot else planned;check('all_windows_required_for_this_publication_scope',len(windows)==expected)
initial=json.loads((o/'extension-decision-initial.json').read_text())['decision']
check('extension_decision_unchanged_after_additional_results',decision==initial)
check('raw_windows_preserved_including_exclusions',validation['windows']==expected+3 and validation['included_windows']==expected and validation['excluded_windows']==3)
excluded={(x['session'],x['mode'],x['bytes']) for x in validation['details'] if not x['included']}
check('only_declared_paired_query_block_excluded',excluded=={('r1-'+p,'query',1048576) for p in 'NTS'})
replacement=[w for w in windows if int(w['physical_rep'])==7]
check('replacement_is_three_fresh_query_windows',len(replacement)==3 and {w['path'] for w in replacement}==set('NTS') and all(w['mode']=='query' and int(w['rep'])==1 for w in replacement))
check('exactly_63_initial_windows',sum(int(w['rep'])<=3 for w in windows)==63)
for w in windows:
 expected_n=6 if not snapshot and mask&(1<<{('query',1048576):0,('kernel',1048576):1,('copy',4096):2,('copy',262144):3,('copy',4194304):4,('resident',2097152):5,('transfer',2097152):6}[(w['mode'],int(w['bytes']))]) else 3
 same=[v for v in windows if (v['path'],v['mode'],v['bytes'])==(w['path'],w['mode'],w['bytes'])]
 check('repetitions_'+w['path']+'_'+w['mode']+'_'+w['bytes'],len(same)==expected_n)
ordered=sorted(windows,key=lambda w:float(w['start_host_utc']));check('no_overlapping_timed_windows',all(float(a['end_host_utc'])<=float(b['start_host_utc']) for a,b in zip(ordered,ordered[1:])))
identities=[];hami_hashes=set();cuda_hashes=set()
for run in sorted(o.glob('r*-*')):
 if not (run/'execution.json').exists():continue
 identity=json.loads((run/'identity.json').read_text());identities.append(identity);label=identity['path'];runtime=json.loads((run/'runtime-libraries.json').read_text());events=[]
 for line in (run/'stdout.txt').read_text().splitlines():
  try:events.append(json.loads(line))
  except ValueError:pass
 check(run.name+'_gpu',identity['gpu_uuid']==protocol['gpu_uuid'])
 check(run.name+'_memory',all(e['total_bytes']==4294967296 for e in events if e.get('event')=='CONDITION'))
 check(run.name+'_cpu_observed',all(x['affinity_status'] and any('0-7' in v if label=='N' else '16-19' in v for v in x['affinity_status'] if v.startswith('Cpus_allowed_list')) for x in runtime))
 for process in runtime:
  for name,digest in process['library_hashes'].items():
   if 'libvgpu' in name:hami_hashes.add(digest)
   if '/libcuda.so' in name:cuda_hashes.add(digest)
 if label in ['N','S']:
  check(run.name+'_limiter_disabled',all(x['environment']['GPU_CORE_UTILIZATION_POLICY']=='DISABLE' for x in runtime))
  check(run.name+'_trace_disabled',all(x['environment']['FLYT_TRACE_REQUESTS'] in [None,'0'] and not x['environment']['FLYT_TRACE_CALLS'] for x in runtime))
  check(run.name+'_hami_mapped',all(any('libvgpu' in n for n in x['library_hashes']) for x in runtime))
 else:
  check(run.name+'_tcp_branch',any(e.get('event')=='TRANSPORT' and e['socktype']==1 and e['connection_is_local']==0 for e in events))
  log=(run/'cell.log').read_text();sm=re.findall(r'Changed SM cores to (\d+)',log)
  check(run.name+'_all_188_SM',bool(sm) and all(x=='188' for x in sm))
  check(run.name+'_no_hami',not any('libvgpu' in n for x in runtime for n in x['library_hashes']))
  check(run.name+'_mps_observed',any('nvidia-cuda-mps-server' in x['command'] for x in runtime))
 cleanup=json.loads((run/'cleanup.json').read_text());check(run.name+'_released',cleanup['released'])
check('same_hami_binary_N_S',len(hami_hashes)==1);check('same_driver_binary',len(cuda_hashes)==1)
vmids=[x['vmi_uid'] for x in identities if x['path']!='N'];check('fresh_independent_VMs',len(vmids)==len(set(vmids)))
check('CPU_counters_cover_all_windows',all(w['cpu_core_seconds'] and float(w['cpu_core_seconds'])>=0 for w in windows))
if snapshot:
 additional=json.loads((o/'additional-native/validation.json').read_text())
 check('additional_native_outputs_preserved_and_valid',additional['status']=='PASS' and additional['windows']==6 and all(x['valid'] for x in additional['details']))
 check('additional_native_released',json.loads((o/'additional-native/r4-N/cleanup.json').read_text())['released'])
report={'status':'PASS' if not errors else 'FAIL','scope':'collected-data snapshot' if snapshot else 'completed campaign','campaign_complete':not snapshot,'windows':len(windows),'additional_native_windows':6 if snapshot else 0,'independent_sessions':len(identities),'expected_windows':expected,'full_protocol_planned_windows':planned,'checks':checks,'errors':errors,'hami_hashes':sorted(hami_hashes),'driver_hashes':sorted(cuda_hashes)}
(o/'bundle-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':report['status'],'windows':len(windows),'errors':errors}));raise SystemExit(bool(errors))
