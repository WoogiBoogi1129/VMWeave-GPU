"""Create the campaign index from analysis CSVs, with explicit scope/limitations."""
import argparse
import csv
import json
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output
def csv_rows(name):
    file=out/'tables'/name
    return list(csv.DictReader(file.open())) if file.exists() else []
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |',*['| '+' | '.join(map(str,row))+' |' for row in rows]])
def number(value):
    return f'{float(value):.3f}' if value else '—'
status=json.loads((out/'tables/analysis-status.json').read_text())
complete=(out/'protocol/MEASUREMENTS_COMPLETE.json').exists() and status.get('primary_formal_runs')==108 and not status['excluded_or_incomplete']
compute=csv_rows('compute-summary.csv');overhead=csv_rows('overhead-summary.csv');interference=csv_rows('interference-summary.csv')
util_summary=[]
for workload in ['long','short']:
    values=[float(r['mean']) for r in compute if r['phase']=='C5-time' and r['workload']==workload and r['metric']=='gpu_utilization_mean_percent']
    if values:util_summary.append(f"{workload}: 설정별 평균 GPU 이용률 {min(values):.2f}–{max(values):.2f}%")
util_text='; '.join(util_summary)
compute_table=table(['측정','커널','설정','n','평균','표본 표준편차','최소–최대'],[
    ['처리율 kernels/s' if r['phase']=='C5-time' else '고정 작업량 초',r['workload'],r['compute'],r['n'],number(r['mean']),number(r['stddev']),number(r['min'])+'–'+number(r['max'])]
    for r in compute if (r['phase']=='C5-time' and r['metric']=='throughput') or (r['phase']=='C5-fixed' and r['metric']=='elapsed_seconds')])
overhead_table=table(['모드','paired n','시간 증가율 평균 %','표준편차 %p','최소–최대 %'],[
    [r['mode'],r['n'],number(r['mean']),number(r['stddev']),number(r['min'])+'–'+number(r['max'])] for r in overhead])
interference_table=table(['모드','VM','paired n','처리율 유지 비율','표준편차','최소–최대'],[
    [r['mode'],r['slot'].upper(),r['n'],number(r['mean']),number(r['stddev']),number(r['min'])+'–'+number(r['max'])] for r in interference])
text=f'''# 실제 GPU 실험 및 발표 자료 — 2026-09-28 캠페인

상태: **{'측정·분석 완료' if complete else '실행 중 — 중간 집계'}**.
새 측정의 완료 기록은 {status['completed_formal_runs']}개, 분석의 주 비교 기록은 {status.get('primary_formal_runs',0)}/108개다.
이 디렉터리의 날짜는 캠페인 시작일이며 개별 실행의 실제 UTC는 원본에 기록돼 있다.
전체 E1–E5 gate 완료나 RPC/MPS/passthrough 세 방식 학습 성능 비교를 뜻하지 않는다.

실제 실행 근거는 [터미널 원본](terminal/), [실행별 원본](runs/), [Prometheus 조회 결과](monitoring/queries/),
[실제 Grafana 캡처·영상](captures/)이다. 요약 그림은 원본에서 만든 보조 자료다.
③·④는 기존 결과를 재사용하고, ⑤·⑥을 새로 측정했다. 과거 데이터와 신규 데이터를 합쳐 반복 수를 늘리지 않았다.

## ① 구현 환경 및 실험 구성

| 항목 | 재현 조건 | 근거 |
|---|---|---|
| 서버 | gpu-4, Xeon Gold 6530 ×2, 64 물리 코어 / 128 논리 CPU, OS 가용 RAM 약 754.5 GiB | [CPU](environment/cpu.json), [RAM](environment/ram.json), [NUMA](environment/numa.json) |
| GPU | RTX PRO 6000 Blackwell Server Edition 4개 중 GPU 1 하나, 제품 96 GB / nvidia-smi 표시 97,887 MiB | [장치 원본](environment/gpu.json) |
| 실제 대상 | `GPU-7d708c42-8d4a-16d5-0746-474567157aa3`, BDF `0000:41:00.0`, NUMA 0 | [실행 매핑 표](tables/gpu-process-mapping.csv) |
| VM A/B | 각각 8 vCPU, RAM 16 GiB, root 16 GiB, Ubuntu 22.04.5, kernel 5.15.0-191 | [게스트 직접 조회](environment/guest-os.json), 실행 manifest/identity |
| 배치 | A→전용 Channel/Worker A, B→전용 Channel/Worker B, 두 Worker→같은 GPU UUID | 실행별 UID·allocation 및 PID→GPU 매핑 |
| 공유 메모리 | Worker당 1세션, region 64 MiB; 각 실행의 layout-summary 및 binary 보존 | `runs/*/layout-summary.json` |
| GPU 요청 | VM/Worker당 메모리 4096 MiB; 연산 25/50/100, 간섭 비교는 모두 50 | manifest, GPU 배정 annotation, 실제 프로세스 환경변수 |
| CPU | VM A 0–7, Worker A 16–19; VM B 8–15, Worker B 20–23; native 0–7 | `runs/*/cpu-pinning.json`, [CPU 계측](tables/cpu-summary.csv) |
| 수집기 | CPU 48–51, exporter 약 1초, Prometheus scrape 1초, Grafana refresh 5초 | [수집기 배치](protocol/monitor-affinity.json), [설정](monitoring/prometheus.yml) |
| Kubernetes / KubeVirt | v1.37.0 / v1.9.0 | [Kubernetes](environment/kubernetes.json), [KubeVirt](environment/kubevirt.json) |
| HAMi / core | v2.10.0 / b216ba1be1b8e21488d1c7370ed3357b3049aad1 대응 libvgpu | [HAMi image](environment/hami-deployment.json), `runtime-libraries.json` |
| NVIDIA / CUDA | 드라이버 580.173.02, workload CUDA 12.8, libcudart 12.8.90 | [드라이버](environment/gpu-driver.json), 실행별 mapping/hash |
| QEMU / 런타임 | custom QEMU 10.1.0 (flyt-ivshmem-qemu-kvm-10.1.0-20.el9), CRI-O 1.37.0 | [QEMU 직접 조회](environment/qemu.json), Kubernetes nodeInfo |
| 가시화 | Prometheus 3.5.0 / Grafana 12.0.2 | [Prometheus](environment/prometheus-version.json), [Grafana](environment/grafana-version.json) |
| 프로그램 | 직접 작성한 동일 CUDA Driver/Runtime API probe, PTX FMA, 2048 blocks × 256 threads | [소스](../../campaign_probe.c) |
| 프레임워크 | 신규 C5/C6에는 PyTorch를 사용하지 않음. 재사용한 9/22 자료는 `2.11.0+flyt.cu128` | [기존 PyTorch 보고서](../../PYTORCH_IMPLEMENTATION_2026-09-22.md) |

```mermaid
flowchart LR
  A[VM A: 8 vCPU / 16 GiB] --> SA[SHM A: 64 MiB / 1 session]
  B[VM B: 8 vCPU / 16 GiB] --> SB[SHM B: 64 MiB / 1 session]
  SA --> WA[Worker A + HAMi]
  SB --> WB[Worker B + HAMi]
  WA --> GPU[Physical GPU 1: same UUID]
  WB --> GPU
```

자체 구현의 출발 commit은 `75b5696fe66e478413efa7ea621a551487e986f0`다.
측정 때 추가된 코드·probe 바이너리·shim의 SHA-256을 각 manifest와 [artifact 목록](protocol/artifact-hashes.json)에 보존했다.
배포 controller는 [새 image digest](protocol/controller-image.txt)를 사용했다. Channel의 `spec.image`는 기존 provision/helper 이미지이므로 controller Deployment 이미지와 혼동하지 않는다.
Worker/guest shim/hook/launcher의 실제 image와 라이브러리 hash는 실행 identity와 runtime-libraries에 있다.
실행 중 디스크에 launcher UID 메타데이터 필드가 추가됐지만 메인 runner가 로드한 코드는
[보존한 원본](protocol/source-loaded/campaign_runtime.py)이다. probe와 실행 동작은 바뀌지 않았다.

## ② 검증 항목 및 조건

| 검증 목적 | 실제 조건 | 판정/측정 기준 |
|---|---|---|
| 출력 정확성 | 결정적 입력 524,288 FP32, 입력/출력 각각 2 MiB; native 기준 출력 3회 hash 확인 | 마지막 출력 전수 비교, `abs(got-ref) ≤ 1e-6 + 1e-4 × abs(ref)`, nonfinite 0 |
| C5 시간제 | long 1,048,576 / short 1,024 FMA 반복; 설정 25/50/100 × 3회; 매회 60초 | 최종 동기화 완료 수 / 단조 시계 elapsed; 이용률은 실제 표본 간격 가중 평균 |
| C5 고정 작업량 | long N=1678 / short N=11339, 설정별 5회 | 같은 N의 완료시간; 마지막 출력 검산은 timer 밖 |
| C6 경로 비교 | long FMA N=1819; native+HAMi 대 VM+SHM+Worker+HAMi; compute 100; mode별 5쌍 | paired `(VM/native−1)×100`; 전체 경로 증가율 |
| C6 공유 간섭 | A seed 2026, B seed 2027, 모두 compute 50 / 4 GiB / 1세션; 각 90초, mode별 단독/동시 5묶음 | 공통 시작 후 15–75초; 완전히 포함된 chunk만 합산; 경계 손실 <1% |
| 준비 실행 | 매 실행 최소 10초 및 50개 커널, 초기화·검산·부팅·회수는 측정 밖 | stdout의 WARMUP / MEASUREMENT 이벤트 구분 |
| 회수 | Channel drain 후 Released, native Pod 삭제 | 실행별 cleanup 및 최종 점검 |

`resident`는 입력 1회 업로드 후 kernel+sync 반복이다. `transfer`는 매 반복 2 MiB H2D→kernel→sync→2 MiB D2H다.
모든 결과는 마지막 출력 검사이며 매 반복 출력 검사를 했다고 해석하지 않는다.
GPU 이용률은 장치 전체 값이다. VM별 성능은 각 probe의 완료 작업 수로 계산한다.
CPU affinity는 통제했지만 메모리 NUMA binding은 통제하지 않았다.
CPU 집합은 affinity이며 OS의 exclusive CPU 예약/격리 설정을 새로 적용한 것은 아니다.
VM/native CPU 0–15는 NUMA 0, Worker CPU 16–23은 같은 소켓의 NUMA 1이다. GPU는 NUMA 0에 연결된다.
따라서 이 배치의 전체 경로 비교에 해당하며, GPU와 Worker가 모두 같은 NUMA node인 결과로 해석하지 않는다.

[동결한 조건](protocol/protocol.json), [단독 실행 순서](protocol/run-order.json), [시간 계측 수정 기록](protocol/protocol-amendments.json)을 함께 확인한다.
guest UTC step에 영향을 받은 원래 long/25/1은 원본에 남기고 동일 조건 clockretry를 주 비교에 사용한다.
이후 단조 시계↔host UTC 대응은 3개 SSH sample 중 최소 RTT를 사용하며 반 RTT를 불확실성으로 보존한다.
반 RTT는 대응 시각의 통신 불확실성이며, 실행 중 시계 drift의 별도 상한을 실측한 값은 아니다.
신규 C5/C6에서도 연산 비율 보장 계약은 확정하지 않았으므로 limiter 판정은 **NOT_EVALUATED**다.

## ③ CUDA 정확성 및 동일 GPU 공유

완료된 신규 실행 {status['completed_formal_runs']}개 중 {status['accuracy_passes']}개가 524,288개 출력의 오차/비유한 값 검사를 통과했다.
[각 실행의 검사 수·최대 오차](tables/runs.csv), [PID→GPU 관측](tables/gpu-process-mapping.csv),
[공유 구간과 시계 오차](tables/sharing-overlap.csv)를 함께 본다. 정확성은 비교한 입력·PTX·경로의 범위에 한정한다.

![신규 90초 공유 실험의 실제 실행 타임라인](figures/sharing-timeline.png)

기존 자료는 별도 날짜로 보존한다: [9/22 tensor 표](reused/pytorch-correctness.csv),
[9/24 두 VM 실제 화면](../2026-09-24-showcase/screenshots/two-vm-gpu-sharing.png),
[당시 보고서](../../IMPLEMENTATION_EXPERIMENT_RESULTS_2026-09-24.md).

![기존 tensor 정확성 표](reused/pytorch-correctness.png)

## ④ 메모리 한도·해제·재할당 — 기존 원본 재가공

1 GiB와 4 GiB의 실제 할당/초과 요청/해제/재할당 원본을 재사용했다.
한도선과 CUDA OOM(2) 설명을 추가하고 HAMi 계상, 관측 GPU process 합계, 장치 전체 메모리를 구분했다.
OOM의 정확한 이벤트 시각이 원본에 없으므로 시계열에 임의의 OOM 시점을 그리지 않았다.

![1 GiB 메모리](reused/memory-1024.png)
![4 GiB 메모리](reused/memory-4096.png)
![합산 요청과 성공량](reused/aggregate.png)

합산 시험은 요청 약 4.8 GiB 중 약 2.4 GiB만 성공한 기록이다.
**한 세션에서 해제한 뒤 다른 동일 세션이 재요청해 성공하는 교대 시험은 실행하지 않았다.**
이 그림으로 해당 동작을 입증하지 않는다. 당시 [실제 화면](../2026-09-24-showcase/screenshots/)과
[재가공 출처·한계](reused/provenance.json)를 함께 제공한다.

## ⑤ 연산 설정값별 관측

실제 Grafana에서 저장된 측정 구간을 조회한 화면:

![compute 100 실제 Grafana 사후 조회](captures/compute-long-3/compute-long-3-grafana.png)

{compute_table}

![전체 이용률 시계열](figures/compute-utilization.png)
![시간제 처리율](figures/c5-time.png)
![같은 작업량 시간](figures/c5-fixed.png)

점은 독립 반복, 검은 표식은 평균±표본 표준편차다. [집계 CSV](tables/compute-summary.csv)에는 실제 n이 있다.
장치 전체 이용률 집계: **{util_text}**.
짧은 커널은 장치를 포화시키는 부하가 아니므로 이 조건만으로 25/50/100 비율 제한을 평가할 수 없다.
설정 숫자는 측정된 GPU 백분율이 아니다. 정책 미판정 상태에서 결과를 제한 보장의 PASS로 바꾸지 않는다.
단독 환경의 설정별 차이와 두 Worker가 있는 환경의 동작을 구분한다.

## ⑥ 전체 실행 경로 오버헤드 및 공유 간섭

![native와 VM의 실제 측정 구간 사후 조회](captures/overhead-resident/overhead-resident-grafana.png)

{overhead_table}

![같은 작업량 경로 비교](figures/overhead.png)

native는 동일 Worker image의 호스트 컨테이너에서 CUDA/HAMi를 사용하는 baseline이다.
순수 SHM 전송 비용이나 개별 API 지연으로 해석하지 않는다. 동일 N·정책·입력·GPU의 paired 원본은
[overhead-pairs.csv](tables/overhead-pairs.csv)에 있다. Worker 추가 CPU 비용은 [별도 표](tables/cpu-summary.csv)에 보존했다.

{interference_table}

![동일 GPU 두 VM 실제 측정 구간 사후 조회](captures/sharing-resident/sharing-resident-grafana.png)

![단독 대비 동시 처리율](figures/interference.png)

처리율 유지 비율은 동시/자신의 단독, slowdown은 그 역수다. pair 전체 처리율과 창 경계 손실은
[interference-pairs.csv](tables/interference-pairs.csv), [runs.csv](tables/runs.csv)에 있다.
동일 설정의 실제 공유 효과를 측정했으며, 자동 정책의 경쟁자 수에 따른 반응과 물리 GPU 경합을 독립 분해하지 않았다.

## 실제 화면과 원본 확인

- 대표 실시간 영상: [compute 100 Grafana 약 42초](captures/compute-100-1/page@9c728d5dd81b508a129c27f9a6c01d83.webm). [영상 시작 UTC·길이](captures/video-catalog.json)를 원본 run 구간과 대조할 수 있다. 전체 실행 영상으로 표기하지 않는다.
- [captures](captures/): 실제 Grafana/실제 stdout 뷰어 PNG·WebM. `live`는 당시 수집 화면, absolute from/to는 본 측정 사후 조회다. 사후 조회를 실시간 실행 영상으로 표시하지 않는다.
- [terminal](terminal/): `script` 실제 출력과 timing의 gzip. 압축 해제 후 `scriptreplay --log-out terminal.txt --log-timing terminal.timing`으로 재생할 수 있다.
- [monitoring](monitoring/): dashboard JSON, datasource/scrape 설정, 이벤트 annotation, 실행별 절대 구간 및 실제 query response.
- [samples](samples/): 원본 GPU/HAMi 관측 및 캠페인 PID만 남긴 CPU 계측. Prometheus 최종 rate 대신 probe elapsed를 최종 통계에 사용했다.
- [runs](runs/): 성공·실패·기준 생성·예비 실행을 함께 보존했다. 기준 생성의 checked_elements=0은 정확성 PASS로 집계하지 않는다.
- [SHA256SUMS](SHA256SUMS): 공개 산출물 검증. private SSH key, cloud-init, Grafana 인증 파일, TSDB 내부 DB는 공개하지 않는다.

## 변경 및 해석상 제한

1. 종료된 Channel을 매번 다시 reconcile하던 controller를 수정해 새 allocation 준비 지연을 줄였다. 삭제 중인 Channel의 finalizer 처리는 유지한다. [검사 기록](protocol/control-tests.txt)과 실제 실행별 정상 회수를 보존했다.
2. 준비 단계에서 status 미생성·이미지 GC·권한 문제를 만났다. pilot 기록은 성능 통계에서 제외했다. never-allocated pilot 한 건은 VMI·allocation·소유 Pod·attachment 부재를 확인하고 UID 조건으로 운영자 정리했다. [해당 기록](protocol/preallocation-failure-cleanup.json)은 정상 회수 PASS로 세지 않는다.
3. 초기 reference의 `native-unlimited` 이름과 `force-disable` 문자열은 잘못된 분류였다. 해당 결과는 native 기준 출력 생성으로만 사용했다. 이후 지원되는 `DISABLE` 설정과 실제 library mapping을 확인했다. **libvgpu 미주입 native baseline은 없다.**
4. fresh guest의 UTC step을 원본에 남기고 단조 시계 대응 및 동일 조건 대체 측정을 적용했다. 최초 일부 run과 이후 clock collector 구성 차이를 숨기지 않는다.
5. live 브라우저 녹화는 같은 host의 별도 CPU 집합에서 대표 구간만 진행했다. 전용 외부 관측 PC에서 모든 반복을 동일하게 녹화한 실험은 아니다. 실제 터미널 원본은 전체 명령 구간을 보존한다.
6. 새 학습 실험, 장애 주입, strict NUMA memory binding, 세션 교대 반환·재시도, limiter 비율 계약 검증, 모든 호출별 지연 분해는 완료하지 않았다. 필요 주장이 해당 항목에 의존하면 추가 실험이 필요하다.

## 재현 및 자료 재생성

측정은 [run_campaign.py](../../run_campaign.py), CUDA 소스는 [campaign_probe.c](../../campaign_probe.c),
배치·명령·회수는 [campaign_runtime.py](../../campaign_runtime.py), 공개 변환은 [export_campaign.py](../../export_campaign.py)에 있다.
현재 클러스터/사전 image·PVC·helper Pod를 전제로 한 캠페인 도구이므로 다른 환경에서 무조건 실행하는 설치 스크립트가 아니다.
키는 새로 생성하고 image/실제 GPU UUID·CPU/기존 점유를 확인한 뒤 준비한다. 기존 run ID를 덮어쓰지 않는다.

```bash
# 저장소 루트. .local 원본을 가진 실행 환경에서 분석/공개 자료를 재생성한다.
.local/evidence-venv/bin/python experiments/evidence/analyze_campaign.py \\
  --base .local/campaign-20260928 --output experiments/evidence/results/2026-09-28-campaign/tables
python3 experiments/evidence/export_campaign.py \\
  --base .local/campaign-20260928 --output experiments/evidence/results/2026-09-28-campaign
python3 experiments/evidence/write_campaign_report.py \\
  --output experiments/evidence/results/2026-09-28-campaign
```

공개 JSONL gzip, 실행별 이벤트/identity, 조건 및 기준 출력만으로도 CSV의 근거를 검토할 수 있다.
공개 자료만 재분석하려면 `analyze_campaign.py --base experiments/evidence/results/2026-09-28-campaign --output /tmp/campaign-check/tables`를 실행한다.
분석기는 gzip 원본도 읽는다. matplotlib가 설치된 Python 환경을 사용하며 시간 창·경계 손실·표본 가중 규칙은 소스에 명시돼 있다.
'''
(out/'README.md').write_text(text)
print(out/'README.md')
