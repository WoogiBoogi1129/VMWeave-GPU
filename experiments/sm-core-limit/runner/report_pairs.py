"""Render the report from audited results, retaining measurement limitations."""
import json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];D=ROOT/'experiments/sm-core-limit';O=D/'evidence/pairs-20261016';s=json.loads((O/'summary.json').read_text());a={r['cap']:r for r in s['aggregate']}
lines=['# 수정된 Core 제한 적용 후 25/75 다중 VM 동시 사용 검증','',
'실험일: 2026-10-16 KST. 두 VM이 하나의 GPU에서 연산하는 구성을 새 VM/Worker로 3회 반복했다. 두 번째 회차에는 VM A/B의 25/75 할당을 뒤집었다. **6개 VM 모두 GPU 연산을 정상 완료하고 Channel을 Released 상태로 회수했다.**','',
f"25% VM의 평균 HAMi 이용률은 **{a[25]['hami_util_mean']:.2f}%**, 75% VM은 **{a[75]['hami_util_mean']:.2f}%**였다. 처리량 비중은 평균 **{a[25]['throughput_share_pct']:.2f}:{a[75]['throughput_share_pct']:.2f}**였다. 따라서 이번 조건에서 두 VM의 사용량이 동일하게 나뉘지는 않았지만, **정확한 25/75 사용률이나 1:3 처리량 배분을 재현했다고 볼 수 없다.**",'',
'## 적용 코드와 검증 범위','',
'- HAMi-core `b216ba1be1b8e21488d1c7370ed3357b3049aad1` + 선형 SM 보정 + idle-reset. [배포용 패치](../../runtime/hami/patches/0001-sm-limit.patch).',
'- 실제 로딩 라이브러리 SHA-256: `f30f08c8f4bbdada1856231f2ec269d50fc81e08881a4146c9c1bbb3173aebd8`. 앞서 빌드한 배포 이미지와 동일한 바이너리다.',
'- VMWeave Guest → SHM → 독립 Worker → 수정 HAMi → 실제 GPU 경로로 실행했다. Worker 프로세스 매핑, Pod UID, 호스트 PID, 제한 환경변수, 동일 GPU 배치를 각각 보존했다.',
'- 각 실험 Worker의 mount namespace에 수정본을 읽기 전용으로 설치하고 SHA를 확인한 뒤 실행 게이트를 열었다. **배포 이미지의 클러스터 전역 롤아웃 시험은 아니다.** 다른 Worker와 기존 서비스의 라이브러리는 변경하지 않았다.',
'- 모든 Worker에서 `GPU_CORE_UTILIZATION_POLICY=FORCE`, `CUDA_DEVICE_SM_LIMIT=25` 또는 `75`를 직접 확인했다. 메모리는 VM당 2048 MiB다.','',
'## 실험 방법','',
'- GPU 2: NVIDIA RTX PRO 6000 Blackwell Server Edition, UUID `GPU-c654d43e-43f8-c28e-77c2-1f17a0cbf46a`, 188 SM. 환경·도구·소스 해시는 [environment.json](evidence/pairs-20261016/environment.json)에 있다.',
'- 회차별 할당 A/B: 25/75 → 75/25 → 25/75. 매번 새 VM과 새 Worker를 생성했다. VM A CPU 32–39, B 40–47; Worker A 48–51, B 52–55로 고정했다.',
'- 같은 PTX 부동소수점 FMA 반복 커널: grid 2048, block 256, 반복 1048576, 매 launch 후 동기화. 결과값을 읽어 동일한 계산 결과인지 확인했다. **PyTorch 학습 실험은 아니다.**',
'- Guest 시각은 SSH 왕복 5회 중 불확실성이 가장 작은 offset으로 보정했다. 두 Guest가 CUDA 초기화를 마친 후 동일한 호스트 기준 시각을 기다리도록 했다. 두 ready 이벤트가 시작 시각 전에 도착했는지도 검증했다.',
'- 회당 180초, 초기 30초 준비. Guest 처리량은 약 150초 측정 구간의 완료 launch 수 / 실제 경과 시간이다. 공통 호스트 이용률 구간은 시작 +35초 이상, +178초 미만이다.',
'- HAMi Worker별 이용률을 주 지표로 사용했다. NVIDIA pmon의 PID별 SM 이용률과 물리 GPU 전체 이용률을 함께 기록했다. 전체 GPU 이용률을 VM별 사용률로 나누어 추정하지 않았다.',
'- 1초 안팎으로 수집하되 센서 내부 갱신 주기와 독립 표본 수는 동일하지 않다. 종합 평균은 회차별 평균 3개의 산술평균이고 표준편차는 그 3개의 표본 표준편차다.','',
'## 결과','',
'| 제한 | HAMi 이용률 평균 ± SD | 설정 대비 차이 | 처리량 평균 (launch/s) | 처리량 비중 |',
'|---|---:|---:|---:|---:|']
for cap,r in a.items():lines.append(f"| {cap}% | {r['hami_util_mean']:.2f} ± {r['hami_util_mean_sd']:.2f}% | {r['hami_util_mean']-cap:+.2f}%p | {r['launches_per_second']:.2f} | {r['throughput_share_pct']:.2f}% |")
lines+=['','| 회차 | A/B 제한 | 25% 측 이용률 | 75% 측 이용률 | 25% 측 launch/s | 75% 측 launch/s | 물리 GPU 이용률 |','|---|---|---:|---:|---:|---:|---:|']
for p in s['pairs']:
 w={r['cap']:r for r in p['workers']};caps='/'.join(str(r['cap']) for r in p['workers'])
 lines.append(f"| {p['pair']} | {caps} | {w[25]['hami_util_mean']:.2f}% | {w[75]['hami_util_mean']:.2f}% | {w[25]['launches_per_second']:.2f} | {w[75]['launches_per_second']:.2f} | {p['device_util_mean']:.2f}% |")
lines+=['','![실측과 제한값 비교](evidence/pairs-20261016/figures/quota-vs-observed.png)','',
'![회차별 Worker 이용률 시계열](evidence/pairs-20261016/figures/worker-utilization.png)','',
'### 교차 계측과 측정 불확실성','',
'`pmon`의 `-`는 0으로 치환하지 않았다. 아래 pmon 평균은 숫자가 존재하는 표본만 사용하므로 누락률에 따라 편향될 수 있으며, 주 판정 지표를 대체하지 않는다. 원문을 함께 보존했다.','',
'| 회차/제한 | pmon 숫자 표본 평균 | 숫자 / 전체 PID 표본 | 마지막 58초 HAMi 평균 |','|---|---:|---:|---:|']
for p in s['pairs']:
 for w in p['workers']:
  n=w['pmon_samples'];m=w['pmon_missing_samples'];lines.append(f"| {p['pair']} / {w['cap']}% | {w['pmon_util_mean']:.2f}% | {n}/{n+m} | {w['last_minute_hami_util_mean']:.2f}% |")
skews=[p['measurement_start_receipt_skew_ms'] for p in s['pairs']]
lines+=['',f"두 Guest의 측정 시작 메시지 호스트 수신 시각 차이는 회차별 {', '.join(f'{x:.1f} ms' for x in skews)}였다. 이는 SSH 전달 지연도 포함하며 GPU 커널 시작 시각을 직접 추적한 값은 아니다. 처리량 구간과 호스트 센서 구간은 위와 같이 구분했다.",'',
'## 해석','',
'1. 수정본이 적용된 VMWeave에서 25/75 제한을 가진 두 VM의 단일 GPU 동시 실행은 확인했다. 실제 적용 여부는 설정 파일만으로 판단하지 않고 라이브러리 SHA, 실행 프로세스 매핑과 환경변수까지 검증했다.',
'2. 25% 측과 75% 측의 이용률·처리량은 구분되지만, 낮은 제한 측은 설정 상한을 초과했고 높은 제한 측은 75%까지 사용하지 않았다. 후자는 75% 사용량을 예약하거나 보장하는 설정이 아니라는 점과 구분해야 한다. 단일 VM의 25/50/75 검증만으로 다중 VM에서도 같은 정확도를 보장할 수 없다는 결과다.',
'3. Core 값은 물리 SM을 25/75로 고정 분할하거나 75% 실행 시간을 예약하는 설정이 아니다. 측정 이용률을 피드백하는 토큰 제어이므로 두 프로세스의 경쟁과 커널 특성에 영향을 받는다. 수정 패치는 SM² 과대 보정과 유휴 적립을 완화하지만 공유 스케줄러 자체를 1:3 가중 스케줄러로 바꾸지는 않는다.',
'4. 잔여 오차의 정확한 원인별 기여도는 이번 실험에서 분해하지 않았다. 커널 실행시간 대신 launch 규모를 차감하는 토큰 모델, 피드백 지연, 두 제한기의 상호작용은 후속 분석 대상이다. 이 결과를 근거로 새로운 원인 하나를 확정하지 않는다.',
'5. 과거 약 50:50 관측과는 GPU UUID·워크로드·실행 조건이 완전히 같지 않으므로 엄격한 수정 전/후 A/B 효과량으로 해석하지 않는다. 이번 보고서의 직접 검증 범위는 수정본의 위 세 회차다.','',
'## 실제 화면과 원시 자료','',
'![동시 실행 중 실제 Grafana 화면](evidence/pairs-20261016/screenshots/live-pair-1/grafana.png)','',
'- [1회차 Grafana](evidence/pairs-20261016/screenshots/pair-1/grafana.png) · [2회차](evidence/pairs-20261016/screenshots/pair-2/grafana.png) · [3회차](evidence/pairs-20261016/screenshots/pair-3/grafana.png). 실제 Prometheus 데이터를 절대 시각 범위로 조회한 화면이다.',
'- [결과 조회 터미널](evidence/pairs-20261016/screenshots/terminal/01-results.png) · [적용 신원과 회수 증거 터미널](evidence/pairs-20261016/screenshots/terminal/02-identity-cleanup.png). 실제 bash/tmux/ttyd로 원본 파일을 조회한 사후 화면이며 실시간 Guest 콘솔로 표시하지 않는다.',
'- [전체 분석 JSON](evidence/pairs-20261016/summary.json) · [HAMi/NVML 원시 시계열](evidence/pairs-20261016/monitor.jsonl) · [pmon 원문](evidence/pairs-20261016/pmon.txt) · [Prometheus 조회 결과](evidence/pairs-20261016/prometheus/queries.json).',
'- [회차 1](evidence/pairs-20261016/pair-1/) · [회차 2](evidence/pairs-20261016/pair-2/) · [회차 3](evidence/pairs-20261016/pair-3/): 각 A/B의 UID, SHA, 환경변수, Worker 로그, Guest 출력, Released 및 cleanup 기록.',
'- [무결성 해시](evidence/pairs-20261016/SHA256SUMS) · [대시보드 정의](pair-dashboard.json) · [그래프 PDF](evidence/pairs-20261016/figures/worker-utilization.pdf).','',
'## 재현 및 자원 정리','',
'실행기는 이 저장소의 검증 노드·이미지·CPU 배치·Guest SSH 키 경로를 사용하는 실험 도구다. 빈 GPU와 기존 카나리 빌드가 필요하다. 이미 완료된 회차 디렉터리가 있으면 덮어쓰지 않고 중단한다.','',
'```sh','bash experiments/sm-core-limit/runner/build_pair_probe.sh','python3 experiments/sm-core-limit/runner/setup_pair_dashboard.py','python3 experiments/sm-core-limit/runner/pair_monitor.py > .local/sm-pair-20261016/monitor.txt 2>&1 &','nvidia-smi pmon -i 2 -s um -d 1 -o DT > .local/sm-pair-20261016/pmon.txt &','python3 experiments/sm-core-limit/runner/run_pairs.py > .local/sm-pair-20261016/campaign.log 2>&1','python3 experiments/sm-core-limit/runner/collect_pair_evidence.py','# 아래는 수집 완료된 원본만 사용하는 오프라인 분석','python3 experiments/sm-core-limit/runner/analyze_pairs.py','.local/evidence-venv/bin/python experiments/sm-core-limit/runner/plot_pairs.py','```','',
'A/B 제한 배치는 25/75 두 회, 75/25 한 회로 완전히 균형 잡힌 설계는 아니다. 세 회의 기술적 반복 결과이며 서로 다른 장비나 GPU 모델의 일반 성능을 대표하지 않는다.','',
'재실행 시 계측 프로세스는 별도로 시작·종료해야 하며, Grafana/Prometheus의 로컬 데이터는 `.local/sm-pair-20261016/`에 남는다. 공개 묶음에는 대시보드 정의, 압축된 Prometheus query_range 응답, 원시 계측과 실제 화면을 보존했다.','',
'[최종 자원 감사](evidence/pairs-20261016/final-audit.json)에서 실험 VM/VMI/Worker/PVC/PV/Profile과 backing 및 GPU 프로세스가 남지 않았음을 확인했다. 기존 VM은 Running이고 기존 Worker의 원본 HAMi SHA도 유지됐다.','',
'모든 회차에서 두 Channel의 Released를 확인한 뒤 VM/PVC/PV와 해당 실험 backing을 제거했다. 기존 VM과 서비스는 유지했다. 후속 검증은 짧은 커널·PyTorch 학습, 긴 시간 실행, 동일 조건 수정 전/후 비교로 확장할 수 있다. 이번 결과는 일반적인 하드 상한이나 모든 작업의 성능 비율 보장이 아니다.','']
(D/'pair-validation.md').write_text('\n'.join(lines))
