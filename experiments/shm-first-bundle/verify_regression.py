"""Check rebuilt defaults and the supplemental two-VM start/stop regression."""
import csv, gzip, math, statistics
from common import *

final=json.loads((OUT/'build/final.json').read_text())
formal=json.loads((OUT/'summary.json').read_text())['summary']['both']
checked=[];missing_wait_telemetry=[]
for name in ['sf-default-both','sf-shared-a','sf-shared-b']:
 p=OUT/'runs'/name
 result=json.loads((p/'execution.json').read_text())
 assert result['exit_code']==0 and result['results']
 assert all(r['status']=='PASS' and r['mismatches']==0 for r in result['results'])
 assert json.loads((p/'channel-released.json').read_text())['status']['phase']=='Released'
 assert json.loads((p/'cleanup.json').read_text())['released']
 runtime=json.loads((p/'runtime-libraries.json').read_text());assert runtime
 for r in runtime:
  assert r['executable_sha256']==final['worker_sha256']
  env=r['environment']
  assert not env.get('FLYT_WAIT_MODE') and not env.get('FLYT_COPY_MODE') and not env.get('FLYT_SPIN_US')
  assert env['GPU_CORE_UTILIZATION_POLICY']=='FORCE'
  assert env['CUDA_DEVICE_SM_LIMIT']==('100' if name=='sf-default-both' else '50')
  assert any('libvgpu' in x for x in r['library_hashes'])
 assert any(line.split()[0]==final['guest_sha256'] and line.split()[1].endswith('/libflyt_guest.so') for line in (p/'guest-artifact-hashes.txt').read_text().splitlines())
 waits=[json.loads(x) for x in (p/'worker-output.txt').read_text().splitlines() if x.startswith('{"event":"FLYT_WAIT"')]
 if name=='sf-default-both':
  waits += [json.loads(x) for x in (p/'stderr.txt').read_text().splitlines() if x.startswith('{"event":"FLYT_WAIT"')]
  assert any(x['role']=='guest-io' for x in waits)
 if name=='sf-shared-b' and not waits:
  missing_wait_telemetry.append(name)
 else:assert any(x['role']=='worker' for x in waits)
 assert all(x['mode']=='bounded' and x['copy']=='optimized' and x['spin_us']==0 and x['spin_calls']==0 for x in waits)
 checked.append(name)

default=[]
p=OUT/'runs/sf-default-both';results=json.loads((p/'execution.json').read_text())['results'];assert len(results)==5
for file in sorted(p.glob('*.csv.gz')):
 mode,size=file.name.removeprefix(p.name+'-').removesuffix('.csv.gz').rsplit('-',1)
 with gzip.open(file,'rt') as f:rows=list(csv.DictReader(f))
 result=next(r for r in results if r['mode']==mode and r['bytes']==int(size))
 assert len(rows)==result['completed'] and all(int(r['sample'])==i for i,r in enumerate(rows))
 fields=[('h2d-'+size,'first_seconds'),('d2h-'+size,'second_seconds')] if mode=='copy' else [(mode,'first_seconds' if mode=='query' else 'second_seconds')]
 for key,field in fields:
  values=[float(r[field])*1e6 for r in rows];assert all(math.isfinite(x) and x>0 for x in values)
  default.append({'metric':key,'mean_us':statistics.mean(values),'formal_both_mean_us':formal[key]['mean_us'],'samples':len(values)})

shared={}
for name in ['sf-shared-a','sf-shared-b']:
 p=OUT/'runs'/name;result=json.loads((p/'execution.json').read_text())['results'][0]
 with gzip.open(p/(name+'-timed.csv.gz'),'rt') as f:rows=list(csv.DictReader(f))
 assert len(rows)==result['completed'] and all(int(r['sample'])==i for i,r in enumerate(rows))
 assert all(math.isfinite(float(r['latency_s'])) and float(r['latency_s'])>0 for r in rows)
 offset=json.loads((p/'identity.json').read_text())['clock_offset']
 shared[name]={'start':result['utc_start']-offset,'end':result['utc_start']-offset+result['elapsed_s'],'rows':rows}
a,b=shared['sf-shared-a'],shared['sf-shared-b']
assert a['start']<b['start']<b['end']<a['end']
windows=[]
for label,lo,hi in [('A before B',a['start']+5,b['start']-5),('A with B',b['start']+5,b['end']-5),('A after B',b['end']+5,a['end']-5)]:
 assert hi>lo
 values=[float(r['latency_s']) for r in a['rows'] if lo<=a['start']+float(r['end_elapsed_s'])-float(r['latency_s']) and a['start']+float(r['end_elapsed_s'])<=hi]
 assert values
 windows.append({'window':label,'start_host_utc':lo,'end_host_utc':hi,'samples':len(values),'mean_ms':statistics.mean(values)*1000,'completed_per_s':len(values)/(hi-lo)})
save(OUT/'regression-validation.json',{'passed':True,'sessions':checked,'default_latency':default,'shared_windows':windows,'missing_worker_wait_telemetry':missing_wait_telemetry,'scope':'One default-policy smoke run and one shared start/stop pair; not additional independent formal repetitions or quota-enforcement evidence. Shared B Worker termination metrics were unavailable after Pod removal; its in-flight hash/environment and output/release evidence were verified.'})
lines=['# 기본 정책 및 다중 VM 회귀 검증','',
 '정식 5회 반복 검증을 통과한 뒤 기본값을 변경하고 Guest/Worker를 다시 빌드했다.',
 '실제 VM에서 wait/copy/spin 환경변수 없이 bounded wait, optimized copy, active spin 0이 선택됨을 확인했다.',
 '계측은 검증을 위해 별도로 켰다. 바이너리 해시, HAMi 정책, 출력 검산, 정상 Released 상태를 모두 대조했다.','',
 '| 항목 | 재빌드 기본값 지연 (ms) | 본 실험 결합 평균 (ms) |','|---|---:|---:|']
for r in default:lines.append(f"| {r['metric']} | {r['mean_us']/1000:.4f} | {r['formal_both_mean_us']/1000:.4f} |")
lines += ['', '## 두 VM 시작·종료 회귀', '',
 'HAMi 상한 50/50에서 A는 120초, B는 약 40초 뒤 시작해 40초 실행했다. 두 VM 결과 검산과 정상 종료를 확인했다.',
 '아래는 전환 경계에서 각각 5초를 제외한 A의 관측값이다. GPU 이용률 상한 준수나 성능 공정성의 통계 검증으로 해석하지 않는다.', '',
 '| 구간 | 완료/초 | 평균 지연 (ms) | 완료 표본 |','|---|---:|---:|---:|']
for r in windows:lines.append(f"| {r['window']} | {r['completed_per_s']:.2f} | {r['mean_ms']:.3f} | {r['samples']} |")
lines += ['', '각 조건을 한 번 수행한 회귀 확인이며 본 실험의 독립 5회 반복에 포함하지 않는다.',
 'B가 먼저 끝난 뒤 A를 기다리는 사이 B Worker Pod가 정리되어 종료 시 누적 계측 로그를 회수하지 못했다. 원시 명령 이력에 NotFound를 보존했다.',
 'B의 실행 중 바이너리 해시·환경·HAMi 매핑, Guest 결과·CSV·정상 Released는 확인했다. 기본값 정책·spin 0의 종료 계측은 단일 VM 및 A에서 확인했다.',
 '향후 수집기는 각 작업 완료 직후 Worker 로그를 확보하도록 보완했다. 성능 측정은 재실행하지 않았다.',
 '[검증 원자료](regression-validation.json) · [최종 빌드와 소스 차이](build/final.json)', '']
(OUT/'REGRESSION.md').write_text('\n'.join(lines))
print('PASS: defaults, output correctness, two-VM overlap and recovery samples')
