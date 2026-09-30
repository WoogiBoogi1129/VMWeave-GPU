"""Write the Korean result report from verified aggregate artifacts."""
import json,sys
from pathlib import Path
root=Path(sys.argv[1]);s=json.loads((root/'analysis/summary.json').read_text());v=json.loads((root/'validation.json').read_text())
def stat(r,k,d=2):return f"{r[k]['mean']:,.{d}f} ± {r[k]['sd']:,.{d}f}"
lines=['# VMWeave 성능 분석 — 2026-09-30 시작 campaign','',
 f"실행·검산·시각 연속성·정상 회수 검증: **{v['status']}**. 전체 계획 완료: **{v['campaign_complete']}**.",
 '**검산 성공과 HAMi 이용률 상한 준수는 별도 판정입니다.** 아래 상한 결과를 함께 확인해야 합니다.','',
 '## 실험 구성','',
 '| 항목 | 조건 |','|---|---|',
 '| GPU | NVIDIA RTX PRO 6000 Blackwell Server Edition, 물리 SM 188개, 동일 GPU UUID |',
 '| 제어기 | 중앙 Go Operator, vmweave.io/v1alpha1 |',
 '| N | 호스트 직접 CUDA + HAMi |',
 '| T | Flyt 기반 TCP/RPC + MPS, 전체 188 SM. 기존 호환성 패치 포함 |',
 '| S | VMWeave SHM + HAMi |',
 '| HAMi 설정 | FORCE, 메모리 4096 MiB, 이용률 상한 25/50/75/100 |',
 '| 반복 | 조건별 독립 5회. 호출 수·1초 표본 수를 독립 반복으로 세지 않음 |',
 '| 단일 VM | 준비 30초 → 120초 실행(중앙 90초 집계) → 고정 작업 2,500회 |',
 '| 다중 VM | A 240초 실행, B는 +60~+180초 부하. B 프로세스/Worker/VM은 회복 관측 후까지 유지 |',
 '| 비교 부하 | 동일 입력·정수 PTX 커널. T는 동일 PTX에서 생성한 cubin 사용 |','',
 f"실제 집계: N/T/S {s['overhead_sessions']} 세션·{s['overhead_measurement_windows']} 측정 구간, 단일 VM {s['single_runs']} 세션, 다중 VM {s['shared_pairs']} 쌍.",
 '[고정 프로토콜](protocol.json) · [N/T/S 시작 시 프로토콜](protocol-overhead.json) · [계획 변경 이력](deviations.json) · [실행 코드](../../../performance/README.md)','',
 '## 단일 VM 이용률 상한','',
 '| 상한 | n | GPU 이용률 평균 (%) | 처리량 (작업/초, 평균 ± SD) | p95 지연 (ms, 실행별 값의 평균 ± SD) | 2,500회 완료 시간 (s, 평균 ± SD) | 상한 판정 |',
 '|---:|---:|---:|---:|---:|---:|---|']
for cap,r in s['single'].items():
 verdict=', '.join(f'{k} {r["enforcement"].count(k)}' for k in ['PASS','FAIL','NOT_EVALUATED','BASELINE'] if k in r['enforcement'])
 util=f"{r['gpu_util_mean']:.2f}" if r['gpu_util_mean'] is not None else '미계측'
 lines.append(f"| {cap} | {r['n']} | {util} | {stat(r,'throughput')} | {stat(r,'p95_ms')} | {stat(r,'fixed_seconds')} | {verdict} |")
lines += ['', '상한 판정은 중앙 구간 평균 이용률 ≤ 설정값 + 10 percentage points, 유효 계측 ≥95%, 정상 작업 완료를 기준으로 합니다. 이 허용오차는 연구용 사전 기준이며 HAMi의 공식 보장값이 아닙니다. 100은 연산 제한 없는 기준(BASELINE)이고, 상한은 처리량 비율이나 코어 독점 할당을 뜻하지 않습니다.', '',
 '![단일 VM 결과](figures/single-caps.png)','',
 '## N / Flyt TCP·RPC / VMWeave SHM 비교','',
 '클라이언트 측 완료 시간을 측정합니다. query는 cudaMemGetInfo, kernel은 launch+sync, H2D/D2H는 각 copy+sync입니다. 표의 크기는 작업 버퍼 크기이며 query 요청의 네트워크 전송량을 뜻하지 않습니다. resident는 GPU 상주 데이터로 kernel+sync를 반복하고, transfer는 매 작업에 H2D와 D2H를 포함합니다. 두 처리량 시험의 커널 내부 반복은 64회이고, 상한·공유 시험은 1,048,576회이므로 두 절의 작업/초를 직접 비교하지 않습니다.','',
 '| 지표 | 크기 (bytes) | N (µs, 평균 ± SD) | T (µs, 평균 ± SD) | S (µs, 평균 ± SD) | S/T 평균 지연 비 |','|---|---:|---:|---:|---:|---:|']
for key,paths in s['overhead'].items():
 mode,size=key.rsplit('-',1)
 if mode in ['resident','transfer'] or not all(p in paths for p in 'NTS'):continue
 ratio=paths['S']['mean_us']['mean']/paths['T']['mean_us']['mean']
 lines.append(f"| {mode} | {int(size):,} | {stat(paths['N'],'mean_us')} | {stat(paths['T'],'mean_us')} | {stat(paths['S'],'mean_us')} | {ratio:.2f} |")
lines += ['', '| 처리량 지표 | N (작업/초, 평균 ± SD) | T (작업/초, 평균 ± SD) | S (작업/초, 평균 ± SD) |','|---|---:|---:|---:|']
for key,paths in s['overhead'].items():
 if not key.startswith(('resident','transfer')) or not all(p in paths for p in 'NTS'):continue
 lines.append('| '+key.split('-')[0]+' | '+' | '.join(stat(paths[p],'operations_per_s') for p in 'NTS')+' |')
lines += ['', 'N도 HAMi를 포함합니다. T의 MPS와 N/S의 HAMi, 큐·동기화·실행기 차이가 포함되므로 결과는 전체 구현 경로의 비교입니다. PTX와 cubin의 계산·입력은 같지만 동일 기계어를 보장하지 않습니다. 전송 매체만의 효과나 모든 CUDA/AI 작업에 일반화하지 않습니다.', '',
 '![호출·전송 지연](figures/path-latency.png)','', '![처리량](figures/path-throughput.png)','',
 '## 다른 VM 부하의 시작·종료','',
 '| A/B 상한, A CPU 슬롯 | n | A 단독 처리량 | 동시 실행 시 A 처리량 | 유지율 | A 단독 p95 (ms) | 동시 실행 시 A p95 (ms) |', '|---|---:|---:|---:|---:|---:|---:|']
for name,r in s['shared'].items():
 def shared_stat(k,percent=False):
  scale=100 if percent else 1
  return f"{r[k]*scale:.2f} ± {r['sd'][k]*scale:.2f}"+('%' if percent else '')
 lines.append(f"| {name} | {r['n']} | {shared_stat('solo_q')} | {shared_stat('shared_q')} | {shared_stat('retention',True)} | {shared_stat('solo_p95_ms')} | {shared_stat('shared_p95_ms')} |")
lines += ['', '각 값은 독립 실행 5회의 평균 ± SD입니다. A는 계속 부하를 실행하는 VM입니다. 역할 교환 실행에서 A의 실제 VM/CPU 슬롯과 상한을 교환합니다. 같은 상한의 단독 구간과 비교하므로 상한 자체의 효과와 공유에 따른 추가 간섭을 구분할 수 있습니다. 25/75를 처리량 1:3 보장으로 해석하지 않습니다.', '',
 '시작 직후 10초의 처리량·p95, 종료 직후 10초의 p95, 회복 시간, Worker Pod에 대응시킨 HAMi 이용률·상한 판정과 PID별 pmon 교차 계측은 [실행별 표](analysis/shared.csv)에 보존합니다. 회복은 기존 단독 처리량의 ±10% 범위에 1초 구간 5개가 연속 들어오는 조건으로 확인합니다. 회복 시간은 다섯 번째 구간의 종료 시점에서 B의 실제 부하 종료 시점을 뺀 값이며, 연속 구간 최초 진입 시간도 별도로 기록합니다. 빈 회복 값은 관측 종료 전 기준을 충족하지 못했다는 뜻입니다.', '',
 '경쟁만으로 이용률이 낮아질 수 있으므로, 공유 상태에서 상한 이하라는 사실만으로 제한 정책 성공을 주장하지 않습니다. 장치 전체 DCGM 값과 VM별 프로세스 이용률을 구분합니다.', '',
 '![50/50 부하 변화](figures/shared-50-50.png)','', '![25/75 부하 변화](figures/shared-25-75.png)','',
 '## 모니터링·실행 증거','',
 'Prometheus 3.5.0, Grafana 12.0.2, DCGM Exporter, HAMi 모니터링, node-exporter를 사용했습니다. GPU·애플리케이션 지표는 1초 수집을 목표로 구성했고, Pod CPU는 중복되지 않는 상위 cgroup 카운터로 수집했습니다. 공유 구간의 VM별 이용률은 Worker Pod와 GPU UUID에 대응시킨 HAMi 지표를 사용하고, 실제 nvidia-smi pmon 원문을 PID와 측정 시간으로 대응시켜 교차 확인합니다. pmon은 요청한 1초보다 실제 간격이 길 수 있으므로 HAMi의 1초 표본 기준과 혼용하지 않습니다. 센서의 내부 갱신 주기와 표본의 독립성은 별개입니다. 원시 표본은 메모리에 모아 측정 후 저장하며, 실제 진행 카운터는 측정 중 1초마다 출력합니다. 따라서 처리량에는 이 계측 비용이 포함됩니다. 짧은 전송 시험의 p99는 표본 수와 함께 참고해야 하며, 전체 지연 표본을 독립 실험 반복으로 세지 않습니다.', '',
 '- [실행별 원본·설정·회수 증거](runs/)와 [실행별 통계](analysis/).',
 '- [실제 Grafana 캡처](captures/): 사전 지정한 첫 반복을 절대 UTC 범위로 조회한 측정 후 화면입니다.',
 '- [검증 결과](validation.json): 원시 표본 건수·출력 검산·시각 연속성·Released 확인.',
 '- [모니터링 자료](monitoring/)와 [터미널 세션](terminal/): 자동 실행 사실을 표시하고 실제 명령·결과를 보존합니다.',
 '- [소스·바이너리 조건](protocol.json): GPU UUID, 이미지 digest, 실제 프로그램 SHA-256을 기록합니다.', '',
 'N/T/S 마이크로벤치마크의 개별 지연은 원시 CSV로 보존하며 Grafana의 last-operation-latency 패널은 단일·공유 부하 시험에서만 채워집니다. 해당 패널의 N/T/S No data를 작업 지연 0으로 해석하지 않습니다. 일반 GPU 이용률과 SM activity는 같은 지표가 아닙니다. HAMi의 상한 100 이용률 계측이 0으로 남는 경우에는 idle로 해석하지 않고 DCGM과 프로세스 계측을 사용합니다. 조회 결과가 없거나 지원하지 않는 지표도 0으로 대체하지 않습니다.', '',
 '예비 실행의 준비 오류·이미지 GC 복구·부하 선택·시계 보정은 별도 이력에 남겼으며 본 실험 반복에 합산하지 않았습니다. SSH 비밀키와 인증 비밀값은 공개 증거에서 제외 또는 마스킹했습니다. 전체 계획 완료 여부와 자원 정리 상태는 검증 결과 및 최종 감사 파일을 기준으로 확인합니다.','']
(root/'README.md').write_text('\n'.join(lines))
print(root/'README.md')
