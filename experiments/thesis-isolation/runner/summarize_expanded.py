"""Recompute original performance stages 5–6 from per-condition raw evidence."""
import csv,hashlib,json,math,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
base=ROOT/'experiments/thesis-isolation/results/20261012-campaign'
out=base/'expanded-full-20261013132650'/'analysis';out.mkdir(exist_ok=True)
plan={'runs':[{**r,'repetition':r['rep']} for r in json.loads((base/'expanded-full-20261013132650/protocol.json').read_text())['plan']]}
rows=[];manifest={};checks=[]
def read(p):
 raw=p.read_bytes();manifest[str(p.relative_to(base))]=hashlib.sha256(raw).hexdigest();return json.loads(raw)
for run in plan['runs']:
 p=base/'pairs'/run['name'];saved=read(p/'results.json');protocol=read(p/'protocol.json')
 assert read(p/'status.json')['state']=='MEASUREMENT_COMPLETE'
 for slot in ['a','b']:
  assert read(base/'runs'/(run['name']+'-'+slot)/'cleanup.json')['released']
 for old in saved:
  condition=old['condition'];events=read(p/(condition+'-observer.json'))
  req=[r for r in events if r['event']=='request'];done=events[-1]
  assert done['event']=='done' and done['attempts']==len(req)
  assert [r['id'] for r in req]==list(range(len(req)))
  ok=[r for r in req if r['code']==0];lat=sorted(r['latency_s'] for r in ok)
  assert all(math.isfinite(x) and x>=0 for x in lat)
  elapsed=done['elapsed_s'];assert elapsed>=1260
  rate=len(ok)/elapsed;p99=lat[math.ceil(.99*len(lat))-1]
  assert len(req)==old['attempts'] and len(ok)==old['successful']
  assert math.isclose(rate,old['throughput_rps'],rel_tol=1e-12) and math.isclose(p99,old['p99_s'],rel_tol=1e-12)
  kernels=0
  if condition!='baseline':
   load=read(p/(condition+'-load.json'));start=read(p/(condition+'-load-start.json'))
   if isinstance(start,list):start=start[-1]
   assert start['event']=='load_started' and start['mode']==condition
   assert load[-1]['op']=='load' and load[-1]['elapsed_s']>=1260
   kernels=load[-1]['completed_kernels'];assert kernels>0
   assert start['received_host_utc']<=req[0]['received_host_utc'] and load[-1]['received_host_utc']>=done['received_host_utc']
  rows.append(dict(run=run['name'],repetition=run['repetition'],direction=run['direction'],condition=condition,order_index=protocol['order'].index(condition)+1,attempts=len(req),successful=len(ok),errors=sum(r['code']>0 for r in req),mismatches=sum(r['code']==-1 for r in req),elapsed_s=elapsed,throughput_rps=rate,p99_ms=p99*1000,load_completed_kernels=kernels,max_abs_error=max(r['max_abs_error'] for r in req)))
for r in rows:
 b=next(x for x in rows if x['run']==r['run'] and x['condition']=='baseline')
 r['throughput_retention_pct']=100*r['throughput_rps']/b['throughput_rps'];r['p99_increase_pct']=100*(r['p99_ms']/b['p99_ms']-1)
assert len(rows)==30 and all(sum(r['direction']==d and r['condition']==c for r in rows)==5 for d in ['ab','ba'] for c in ['baseline','memory','compute'])
with (out/'per-run.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
groups=[]
for direction in ['ab','ba','all']:
 for condition in ['baseline','memory','compute']:
  selected=[r for r in rows if r['condition']==condition and (direction=='all' or r['direction']==direction)]
  g={'direction':direction,'condition':condition,'repetitions':len(selected),'successful':sum(r['successful'] for r in selected)}
  for key in ['throughput_rps','p99_ms','throughput_retention_pct','p99_increase_pct']:
   vals=[r[key] for r in selected];g[key]={'mean':statistics.mean(vals),'min':min(vals),'max':max(vals),'sample_sd':statistics.stdev(vals)}
  groups.append(g)
summary={'scope':'Expanded-load performance experiment, separate from original P and calibration pilots','raw_audit':'PASS','conditions':len(rows),'attempts':sum(r['attempts'] for r in rows),'successful':sum(r['successful'] for r in rows),'errors':sum(r['errors'] for r in rows),'mismatches':sum(r['mismatches'] for r in rows),'all_sample_targets_met':all(r['successful']>=10000 for r in rows),'groups':groups,'service_suitability':'INCONCLUSIVE'}
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(out/'source-sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
lines=['# 확대 부하 성능 경합 — 본실험 집계 결과','', '현재 계획서에서 재번호화한 데이터 접근 격리 E2와 구분되는, 대화에서 승인한 성능 실험이다.','',f"방향별 5회, 30구간을 원시 요청 기록으로 재계산했다. 총 {summary['successful']:,}건 정상 완료, 오류 {summary['errors']}건, 결과 불일치 {summary['mismatches']}건. 모든 구간이 1,260초 이상이며 10,000건을 충족했다. 세션 20개 회수 기록을 확인했다.",'','## 방향별 결과','', '| 방향 | 조건 | 반복 | 처리량 평균 (건/초) | 반복별 p99 평균 (ms) | 기준 대비 처리량 유지율 평균 | p99 증가율 평균 |','|---|---|---:|---:|---:|---:|---:|']
for g in groups:
 lines.append(f"| {g['direction']} | {g['condition']} | {g['repetitions']} | {g['throughput_rps']['mean']:.4f} | {g['p99_ms']['mean']:.3f} | {g['throughput_retention_pct']['mean']:.3f}% | {g['p99_increase_pct']['mean']:.3f}% |")
lines+=['','ab는 A 측정/B 부하, ba는 B 측정/A 부하이다. all은 10개 반복의 동일 가중 평균이다.','', '## 계산과 검증','', '- p99는 각 구간 정상 요청 지연시간의 nearest-rank 99백분위수이며 표는 그 반복별 값의 평균이다. 전체 요청을 합친 p99가 아니다.', '- 처리량은 정상 완료 수/관측 경과 시간이다. 지연시간은 GPU forward와 동기화까지이며, 정확성 확인을 위한 CPU 전송·비교는 지연시간에서 제외되고 처리량의 경과 시간에는 포함된다.', '- 변화율은 동일 반복의 기준 조건과 짝지어 계산한 뒤 평균했다. 원시 수치와 기존 results.json의 일치, 요청 ID 연속성, 구간 길이, 조건 수, 역할별 반복 수를 확인했다.', '- 경합 조건은 부하 시작/종료의 호스트 수신 시각이 관측 구간을 포함하고 실제 커널 완료 수가 양수임을 확인했다. 수신 시각에는 통신 지연이 포함된다.', '- per-run.csv에 반복별 값, summary.json에 평균·최솟값·최댓값·표본 표준편차, source-sha256.json에 입력 증거 해시를 보존했다.','', '## 해석 범위','', '- 표본 수 목표는 충족했지만 요청 간 자기상관과 방향별 5회라는 반복 수 제한이 있다. 신뢰구간이나 통계적 유의성을 주장하지 않는다.', '- 이 결과는 해당 MLP, 부하 구현, VM 배치와 할당량에서의 관측이다. 부하가 GPU 대역폭/연산을 포화시켰다는 증거 또는 모든 작업의 격리 보장은 아니다.', '- 서비스 SLA가 없어 적합성은 INCONCLUSIVE다. 메모리 접근 차단·기밀성·무결성 경계를 검증한 결과로 해석하지 않는다.', '- 8번의 스크린샷·최종 보고서·GitHub 반영은 이 집계에 포함하지 않았다.']
(out/'analysis.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='groups'},indent=2))
