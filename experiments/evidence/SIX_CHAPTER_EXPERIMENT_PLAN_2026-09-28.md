# 6장 자료 보완을 위한 실험 계획

작성일: 2026-09-28. 상태: **고정 작업량 사용자 중단, 확보 자료 정리**.
현재 사용 가능한 화면·영상·그래프와 미실행 범위는 [시각 자료 목록](VISUAL_EVIDENCE_INVENTORY_2026-09-28.md)을 따른다.
기준: [6장 근거 점검](SIX_CHAPTER_EVIDENCE_AUDIT_2026-09-28.md), [9월 24일 결과](IMPLEMENTATION_EXPERIMENT_RESULTS_2026-09-24.md).
이 문서는 여섯 장의 부족한 자료를 채우는 후속 계획이다. 과거 결과와 판정을 소급 변경하지 않는다.
실제 실행·변경 조건·산출물은 [후속 캠페인](results/2026-09-28-campaign/)에 기록한다.

### 이번 실행에 적용하는 범위와 변경

- ③·④의 대규모 반복 재실험은 제외한다. 9월 22일 정확성과 9월 24일 메모리·공유 원본을 재가공하고 당시 실제 화면에 연결한다. 아래 C3/C4 상세 절차는 확장 계획으로 보존하며 이번 완료 항목으로 세지 않는다. 세션 간 해제 후 재시도는 기존 자료로 입증하지 않는다.
- 신규 실행은 ⑤ 시간제 18회·고정 작업량 30회, ⑥ 직접/VM 비교 20회·공유 30묶음(40개 VM 실행)이다. 기준 출력·예비 실행은 별도다.
- C6의 정수 미세 커널은 native 호출이 지나치게 짧아 예비 실행 후 **동일 긴 FMA**로 변경했다. 이 변경과 고정 작업량은 첫 반복 측정 전에 `protocol.json`에 동결했다. final output 524,288개 전수 비교를 수행한다. 매 iteration 출력의 별도 정확성 시험을 수행했다고 주장하지 않는다.
- CPU affinity는 VM A 0–7 / Worker A 16–19, VM B 8–15 / Worker B 20–23, native 0–7이다. 메모리 NUMA는 관측하며 strict membind는 적용하지 않는다. 전체 E1–E5 성능 gate 완료와 구분한다.
- 실제 topology에서 VM/native CPU는 NUMA 0, Worker CPU는 같은 소켓의 NUMA 1이다. GPU는 NUMA 0이다. 이 배치를 모든 조건에 고정하며, 전 경로의 동일 NUMA node 배치로 표기하지 않는다.
- native baseline은 **호스트 컨테이너 + HAMi**이다. `native-hami-disabled`는 `DISABLE` 환경변수와 실제 libvgpu mapping을 보존한 예비 조건이며, libvgpu 미주입 baseline은 실행하지 않았다. 초기에 `native-unlimited`라 명명한 기준 생성은 지원되지 않는 정책 문자열을 사용했으므로 무제한 baseline으로 분류하지 않는다.
- 부팅 직후 guest UTC step을 발견해 단조 시계와 host UTC를 대응시키는 읽기 전용 collector를 추가했다. 영향을 받은 첫 long/25 실행은 보존하고, 동일 조건 대체 실행을 사전에 기록했다. 원래 측정의 단조 시계 처리율은 유효하지만 해당 GPU 시간 정렬은 제외한다.
- 실제 `script` 터미널 출력·타이밍, Prometheus 원본, Grafana 브라우저 캡처를 보존한다. 브라우저 로그 뷰어는 실제 stdout을 표시하며 데스크톱 터미널 녹화라고 부르지 않는다. 전용 외부 녹화 PC는 사용하지 않았고 대표 live capture는 host CPU 48–51에서 수행했다. 모든 반복을 시작부터 회수까지 화면 녹화했다는 주장은 하지 않는다.

신규 학습 tensor 비교·장애 주입은 추가하지 않고, 기존 PyTorch 결과는 날짜·버전을 명시해 재가공한다.
새 정확성 시험은 CUDA probe의 정수/부동소수점 출력 검증이다.

**시각 자료 방침 수정:** 실제 명령을 실행하는 터미널과 Prometheus/Grafana의 실측 화면을 주 자료로 삼는다.
실행 명령→진행 과정→결과→자원 회수의 흐름을 화면에서 확인할 수 있게 하고, 정적 SVG/PDF는 요약용으로 보조한다.
아래 모니터링·녹화 구성은 구축 계획이며, 현재 설치·수집이 완료됐다는 뜻은 아니다.

## 실행 순서와 완료 기준

| 순서 | 작업 | 의존 관계 | 완료 기준 |
|---|---|---|---|
| 1 | 기존 증거 재가공, 환경 수집, ① 배치도·② 조건표 | 기존 공개 결과 | 환경 조회 터미널 기록, 조건 표·배치도, 재현 조건 묶음 |
| 2 | 공통 계측·정책·CPU 배치, Prometheus/Grafana·터미널 녹화 준비 | 신규 probe/runner·exporter 개발 | 예비 실행의 명령/실측/결과가 같은 run ID로 연결된 화면·원본, 버전 동결 |
| 3 | ③ 단일/두 VM 정확성·동시 사용 | 공통 계측 | mismatch 수와 실제 작업 구간이 기록된 반복 결과·타임라인 |
| 4 | ④ 메모리 이벤트·세션 간 재사용 | 공통 계측, ③ 경로 확인 | 1/4 GiB 단계별 결과와 양방향 세션 반환·재할당 증거·그림 |
| 5 | ⑤ 연산 설정별 특성 | 출력 검산·정책 식별·대조 부하 준비 | 이용률·처리율·고정 작업량 시간·정확성, 정책 판정 또는 미판정 사유 |
| 6 | ⑥ 오버헤드·공유 간섭 | 정확성 확인, 동일 정책·CPU 배치, calibration | 동일 조건의 독립 반복 비교 및 변동 범위·그래프 |

각 장은 **원본 + 조건 manifest + 분석 CSV + 실제 터미널/관측 화면 + 판정/한계**가 있어야 완료로 처리한다.
③~⑥은 장별 대표 실험의 연속 화면 녹화도 확보한다. 모든 반복의 원본은 별도로 보존한다.
실험 완료와 가설의 PASS는 별개다. 제한이나 성능 개선을 입증하지 못한 결과도 충분한 측정·그림이 있으면 결과 자료로 보고한다.

## 실제 수행 과정을 보여 주는 시각 자료 수집

### 기본 화면 구성과 기록 방식

대표 시연은 한 화면에 다음 세 영역을 배치한다. 자동 실행은 runner 명령과 그 출력으로 보여 주고, 실제 수동 실행은 입력부터 기록한다.

| 화면 영역 | 표시 내용 |
|---|---|
| 왼쪽: 실험 터미널 | host/guest 이름, UTC, run ID, commit/image 참조, 실제 실행 명령·인자, 단계 이벤트, 요청 bytes·CUDA 반환값·정확성 결과, exit code |
| 가운데: 자원 확인 터미널 | `kubectl`의 VM/Channel/Worker 상태, host `nvidia-smi`의 대상 UUID·process 목록, PID→Worker 매핑, 종료 후 Released·잔여 process 확인 |
| 오른쪽: Grafana | run/VM/Worker/GPU 필터, 절대 UTC 구간, GPU/HAMi/앱 지표, 실제 이벤트 annotation, 수집 상태·최근 표본 시각 |

- 터미널은 `tmux` 등으로 분할하고 `script`의 출력·타이밍 기록 또는 `asciinema` cast를 보존한다. 이를 원본 명령 stdout/stderr·결과 JSON과 함께 저장한다. 사용할 도구·버전·녹화 방식은 설치 확인 후 고정한다.
- 화면 녹화는 명령 실행 전부터 시작해 초기 상태→작업→결과→정상 회수까지 연속 기록한다. 터미널과 브라우저를 함께 보이는 화면 녹화 도구를 사용한다. 기존 브라우저 전용 녹화는 보조 자료로 유지한다.
- 각 장에 대표 정지 화면 2~4장과 원본 영상 1개 이상을 확보한다. 발표용 30~90초 발췌에는 원본 run ID·영상 timecode를 붙이고 전체 영상도 보관한다.
- 대표 화면은 사전 순서의 첫 유효 실행을 기준으로 선정한다. 준비 실패·OOM 예상 오류·정책 미판정도 해당 의미가 보이도록 보존하고 결과가 좋은 반복만 골라 제시하지 않는다.
- 읽을 수 있는 글자 크기와 패널 수를 우선한다. 장별 상세 화면을 별도로 캡처하고, 선택 영역을 잘랐다면 원본 전체 화면도 보관한다.
- 기능 시연 녹화와 성능 본 측정은 실행 ID를 분리한다. 성능 본 측정은 같은 collector 설정으로 진행하고, 무거운 브라우저 녹화는 관측용 별도 PC에서 수행하거나 별도 시연에 한정한다.
- 성능 본 측정 종료 후 실제 저장 구간을 Grafana에서 열어 캡처한 화면은 **본 측정 사후 조회**라고 표기한다. 별도 시연의 영상에 본 측정 run ID나 수치를 붙이지 않는다.
- 화면 제목은 `실시간 실행`, `본 측정 사후 조회`, `기존 로그 재가공`을 구분한다. 9월 24일 자료는 당시 자료로 표시한다.

### Prometheus/Grafana 준비와 수집 경로

9월 24일 보고서는 당시 Grafana가 없어서 자체 읽기 전용 대시보드를 사용했다고 기록한다.
새 실행 전 Prometheus/Grafana/DCGM exporter의 **현재 설치 여부·접근 가능성·버전**을 확인한다.
사용 가능한 기존 인스턴스가 있으면 별도 실험 dashboard/job을 추가하고, 없으면 실험용 Prometheus/Grafana를 준비한다.
이미지·설정·dashboard JSON은 버전을 고정한다. 실험 노드에 두는 경우 CPU/메모리 비용을 기록하고 workload CPU 집합과 분리한다.

1. **GPU 장치 지표:** 실제 사용 가능한 DCGM exporter 또는 host NVIDIA 조회 기반 exporter에서 UUID별 이용률·메모리·clock/power를 가져온다. 같은 값을 두 수집기에서 중복 합산하지 않는다.
2. **HAMi 지표:** 기존 HAMi monitor의 `/metrics`에서 container 메모리·이용률을 수집한다. 실제 metric/label/단위는 endpoint에서 확인해 `metric-map.json`에 저장한다.
3. **앱·실험 지표:** runner/guest의 JSONL 이벤트를 읽는 전용 exporter를 구현한다. run/VM/session별 성공 할당량, quota·compute 설정, 완료 작업 수, 측정 상태·결과를 노출한다. 이는 **신규 구현 항목**이며 기존 GPU exporter가 제공한다고 가정하지 않는다.
4. **상태·매핑:** VM/Channel/Worker UID, host PID/cgroup, GPU UUID를 연결한다. 장치 전체 utilization과 VM별 완료 작업 수를 별도 패널로 둔다.
5. **수집 검증:** 실험 job의 scrape는 목표 1초, timeout은 interval 이하로 설정한다. exporter 갱신·scrape·Grafana 갱신은 서로 다른 주기임을 표시한다. 브라우저는 기본 5초 갱신으로 두고 측정 원본 해상도와 구분한다.

아래 metric 이름은 exporter 설계안이다. 실제 구현 후 `HELP/TYPE`, label·단위를 검증하고 이름을 동결한다.

| 제안 지표 | 원천·의미 | Grafana 표시 |
|---|---|---|
| `flyt_evidence_allocated_bytes` | 앱 이벤트 장부의 현재 성공 할당량, session별 gauge | 세션 누적 할당량. 실제 Worker VRAM 계상과 구분 |
| `flyt_evidence_quota_bytes`, `flyt_evidence_compute_setting` | 실행 manifest와 실제 배정 대조 | 한도선·설정값, 실측 이용률과 구분 |
| `flyt_evidence_completed_work_total` | 동기화 완료한 커널/작업의 누적 counter | 실시간 처리율 참고 패널. 최종 처리율은 원본 완료 수/정확한 측정시간 사용 |
| `flyt_evidence_run_active`, `flyt_evidence_mismatches_total` | 실제 실행 상태·검사한 불일치 수 | 실행 상태 타임라인·검사 수와 함께 정확성 표 |
| `flyt_evidence_elapsed_seconds`, `flyt_evidence_throughput` | 종료된 run의 원본 결과 요약 | 완료 run별 시간·처리율 비교, 종료 후 계산값임을 표시 |
| `flyt_evidence_last_event_timestamp_seconds` | exporter가 마지막으로 읽은 원본 이벤트 시각 | 데이터 신선도·수집 지연 표시 |

label은 campaign/run/VM/session/backend/workload 등 유한한 실험 식별자에 한정한다.
종료 결과는 완료 상태로 보존해 회수 후에도 확인할 수 있게 하고 active 상태는 종료 즉시 해제한다.
scrape 실패·오래된 exporter 값·미검사 정확성은 0 또는 PASS로 채우지 않는다.
OOM처럼 scrape 사이에 끝나는 이벤트는 gauge만으로 기록하지 않고 원본 이벤트와 Grafana annotation으로 보존한다.

### Dashboard·증거 보존 기준

- dashboard는 **실행/공유**, **메모리**, **연산 설정**, **오버헤드/간섭** 4종으로 나누고 공통 변수 campaign/run/VM/GPU를 둔다.
- start, measurement start/end, allocate, OOM, free, reallocate, release를 원본 이벤트의 host 대응 시각으로 annotation 처리한다. 오차·source event ID도 annotation에 연결한다.
- Prometheus Targets/`up` 확인 화면과 metric 이름·label이 보이는 조회 화면을 캠페인마다 1회 보존한다. 이는 수집 연결 증거이며 workload 정확성 판정을 대신하지 않는다.
- 캡처마다 `capture-manifest.json`에 run ID, 촬영 UTC, 절대 from/to, dashboard UID·JSON hash, 변수, panel query, 원본 이벤트/metric 결과 경로, 영상 timecode를 기록한다.
- dashboard JSON과 datasource/scrape 설정만으로 데이터가 보존되는 것은 아니다. 해당 시간의 Prometheus range query JSON/CSV, 원본 exporter/snapshot, 이벤트 JSONL을 함께 내보낸다.
- 실제 화면 PNG·영상, terminal 출력·타이밍 파일, query 결과, 분석 CSV의 hash를 묶는다. 비밀값이 포함되지 않는 실험용 터미널을 사용한다.
- Grafana 준비가 지연되면 기존 읽기 전용 dashboard와 터미널로 기능 기록을 먼저 수집할 수 있다. 이때 Grafana 자료는 미완료로 남기고, 자체 화면을 Grafana 화면이라고 표기하지 않는다.

구성 근거: [Prometheus scrape 설정](https://prometheus.io/docs/prometheus/latest/configuration/configuration/),
[Grafana annotation](https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/annotate-visualizations/),
[Grafana dashboard/panel 공유](https://grafana.com/docs/grafana/latest/visualizations/dashboards/share-dashboards-panels/).
실제 설치 버전에서 제공되는 기능을 확인하며, 화면 PNG는 브라우저 캡처로도 확보해 별도 렌더링 플러그인을 필수로 두지 않는다.

## 공통 실험 계약

### 고정 조건

- 노드 `gpu-4`, 대상 GPU UUID `GPU-7d708c42-8d4a-16d5-0746-474567157aa3`. 장착 GPU 4개 중 1개를 사용한다. 실행 전에 현재 UUID/BDF/NUMA와 기존 소유권을 재확인한다.
- VM당 8 vCPU / RAM 16 GiB / root 16 GiB / Ubuntu 22.04.5. 이전 버전을 그대로 쓸 경우 kernel 5.15.0-191-generic과 이미지 digest까지 확인한다. 변경됐다면 새 조건으로 기록한다.
- 기본 1 VM, 공유 조건 2 VM. 각 VM은 독립 Channel/PVC/Worker를 사용한다. Worker당 기본 1세션·backing 64 MiB, 합산 시험은 2세션·128 MiB. 실제 backing/BAR 크기도 수집한다.
- 기본 GPU 한도 4096 MiB·compute 50. 메모리 단독 시험은 compute 100, 연산 시험은 25/50/100, direct 비교는 정책 동등화 조건을 별도로 적용한다.
- controller/guest shim/Worker/hook/launcher/probe·분석 코드의 commit, 미커밋 소스 hash, image digest, binary hash를 동결한다. 런타임 변경 시 새 campaign으로 구분하고 변경 전후 반복을 합치지 않는다.
- VM vCPU와 Worker 4 CPU 예산은 실제 affinity/cpuset으로 검증한다. Kubernetes CPU request/limit만으로 pinning을 주장하지 않는다. VM A/B, Worker A/B의 CPU 집합은 겹치지 않게 배치하고 SMT sibling 중복도 확인한다.
- GPU 인접 NUMA의 코어가 부족하면 같은 소켓 내 고정 배치를 사용하고 원격 NUMA 접근을 기록한다. 단독 실행에서도 동시 실행용 CPU 집합을 유지하며 유휴 B의 코어를 A에 추가하지 않는다.
- 다른 GPU 작업, GPU clock/temperature/power, host 부하·계측 CPU 사용을 기록한다. 외부 부하가 겹친 반복은 삭제하지 않고 측정 유효성을 별도 표시한다.

### 시간·반복·판정

- 모든 이벤트에 `run_id`, guest monotonic ns, guest UTC, host 수신 UTC/monotonic을 저장한다. 실행 전후 왕복 clock probe로 guest→host 시각 대응과 오차 범위를 산출한다. NTP 상태만으로 동기화를 가정하지 않는다.
- 공유 타임라인은 관측 오차를 포함한다. 보수적인 동시 구간은 `min(각 종료 하한) - max(각 시작 상한)`으로 계산한다. 이는 두 workload의 겹침이며 커널의 물리적 동시 상주를 입증하는 지표는 아니다.
- GPU/HAMi collector는 **목표 1초 주기**로 분리한다. 각 조회의 시작·완료·실제 간격·실패·원본 시각을 저장하고, 지연된 값을 보간해 실측처럼 사용하지 않는다. HAMi 지표의 실제 갱신 주기도 기록한다.
- CPU/cgroup·PID→Worker 매핑은 별도 수집한다. 장치 전체 값은 VM별 값으로 복제하지 않는다. 그래프에 앱 할당량/Worker process/HAMi/물리 GPU를 구분한다.
- calibration·준비 실행은 본 측정과 다른 디렉터리에 저장한다. compute는 10초, 성능 시험은 최소 10초이면서 50회 이상 준비 실행 후 측정한다. 준비 실행 중 사용한 세션을 유지해 측정한다.
- 기능·메모리·고정 작업량 성능은 조건별 독립 5회, 연산 시간제 관측은 기존과 비교할 수 있도록 조건별 3회 수행한다. 독립 반복마다 새 VM/allocation 또는 새 native 프로세스를 사용한다.
- 성능은 반복별 원본·평균·표본 표준편차·최소/최대를 표시한다. 한 실행의 1초 이용률 표본을 독립 반복으로 세지 않는다. 순서는 사전 생성한 seed 20260928의 균형 순서표로 교차한다.
- `execution`, `correctness`, `measurement_validity`, `enforcement`, `cleanup`을 각각 판정한다. OOM 예상 오류는 시험 성공일 수 있다. 준비 실패·측정 실패·결과 불일치는 따로 보존하고 재시험에는 새 ID를 부여한다.
- 성능 계측은 시작/종료 이벤트와 완료 작업 수 중심으로 한다. 상세 API trace와 영상 캡처는 기능 시연용 별도 실행에서 수행한다. collector on/off 예비 비교로 계측 영향을 보고하고, 계측 설정을 본 측정 중 바꾸지 않는다.
- 정상 drain→Released→실행 Pod 종료→backing 회수·GPU process 정리를 확인한다. 회수 불명확 시 다음 실행을 중단하고 실패 기록을 남긴다. 기존 보존 자원이나 finalizer를 강제로 변경하지 않는다.

## ① 구현 환경 및 실험 구성: C1

**목적:** 발표의 배치도와 환경 표를 실제 실행 환경·버전에 연결한다. GPU 부하 실험은 필요하지 않다.

1. `lscpu -J`, `free -b`, OS/kernel, `kubectl version -o json`, KubeVirt 상태, CRI-O, NVIDIA driver/GPU inventory를 수집한다. CUDA toolkit/runtime·실제 로딩 library와 PyTorch wheel metadata를 구분한다.
2. HAMi release/image, HAMi-core library hash·mapping, QEMU build/version과 ivshmem 장치 지원을 보존한다. 새 이미지를 사용하면 guest 내부 패키지·kernel도 다시 기록한다.
3. VM A/B→Channel/PVC→Worker Pod UID→host PID/cgroup→GPU UUID 매핑을 수집한다. 각 runtime artifact가 manifest의 hash와 일치하는지 확인한다.
4. SHM/HAMi 배치도를 SVG/PDF로 작성한다. 장착 4 GPU 중 대상 1 GPU, 단일/공유 모드, guest RAM과 GPU memory quota를 구분한다. 기존 RPC/MPS 그림을 대체할 새 파일로 만든다.

**실제 화면:** 환경 조회 터미널에 `hostname`, UTC, 버전 조회 명령과 GPU 4개 inventory를 남긴다. VM/Worker 매핑 조회도 별도 화면으로 보존한다.
**산출물:** `environment.json`, `versions.json`, `placement.json`, `artifact-hashes.json`, `environment-table.csv`, `deployment.svg/pdf`, 환경 조회 terminal 기록·PNG.
**완료 기준:** 모든 표 항목에 조회 시각·근거 파일이 있고 A/B가 같은 UUID에 연결된다. 본 슬라이드는 배치도·재현 조건 표 중심으로 유지하며 환경 조회 화면은 근거 부록에 둔다. 결과 수치·성능 그래프는 넣지 않는다.

## ② 검증 항목 및 조건 확정: C2

**목적:** 조건 차이와 측정 범위를 사전에 고정한다. 아래 조건표를 발표의 목적–조건–판정 표로 축약한다.

| ID·검증 목적 | 고정 조건·반복 | 판정 기준 |
|---|---|---|
| C3-S 단일 CUDA 정확성 | 1 VM, 4 GiB/compute 50/1세션, 기존 4096 B copy·정수 PTX, 45초×5회 | API 성공, 전 바이트·매 커널 mismatch 0 |
| C3-P 두 VM 공유 | 각 4 GiB/50/1세션, seed 2026/2027, 각 45초, pair×5회 | 각각 correctness PASS, 같은 UUID, 다른 Worker, 보수적 공통 작업 구간 ≥40초 |
| C4-M 메모리 이벤트 | 1/4 GiB, compute 100/1세션, 각 stage 15초, 한도별 5회 | 경계·초과·해제·재할당·앱 계상 복원, 예상 CUDA 반환 |
| C4-X 세션 교대 | 4 GiB/100/2세션, 요청량 각 2,576,980,377 B, A선행/B선행 각 5회 | 두 번째 요청 OOM, 선행 해제 후 같은 후행 세션 재요청 성공 |
| C5-T 설정별 시간제 부하 | 4 GiB/1세션, 25/50/100 × 긴/짧은 FMA × 3회, warm-up 10초+측정 ≥60초 | 출력 정확성·측정 유효성; 제한은 별도 정책 계약으로 판정 |
| C5-N 동일 작업량 | 동일 6조건×5회, workload별 고정 N 커널 | 같은 입력·N·정확성, 최종 동기화까지 시간 |
| C6-A direct/VM 비교 | native+동등 HAMi/VM SHM+HAMi, resident/transfer, 각 5회 | 동등 정책·고정 N·정확성, 시간비와 변동 범위 |
| C6-B 공유 간섭 | A 단독/B 단독/A+B, 각 VM 4 GiB/50/1세션, 각 5회 | 동일 자원·작업, 공통 60초 처리율, 정확성 |

C3의 40초는 이번 계획의 **동시 실행 입증용 기준**이며 기존 결과의 소급 합격 기준이 아니다.
연산 제한의 대상 지표·시간 창·허용오차는 C5 사전 조사에서 source/binary 정책에 근거해 `policy-contract.json`에 확정한다.
정책이 이용률 상한인지 연산량/시간 분배 목표인지 불명확하면 `NOT_EVALUATED`로 유지하고, 특성 관측만 진행한다.
소스에 명시된 허용오차가 없을 경우 채택한 공학적 기준임을 표시하고 설정별 본 측정 전에 동결한다.
결과를 본 뒤 통과하도록 허용오차를 변경하지 않는다.

**실제 화면:** runner가 실행 전 출력하는 조건 요약과 실제 적용된 VM/Worker 자원 조회를 터미널에 나란히 표시한다. run ID·quota·compute·session·반복 번호를 읽을 수 있게 캡처한다.
**산출물:** `campaign.json`, `conditions.csv`, `run-order.csv`, `policy-contract.json`, `validation-matrix.svg/pdf`, `conditions-terminal.png`와 terminal 원본. 본 슬라이드는 조건표로 구성하고 화면은 근거 부록으로 연결한다.

## ③ CUDA 정확성 및 두 VM 공유: C3

### 기존 자료 재가공

- 9월 24일 smoke 결과에서 API/입력 bytes/커널 반복 수/실행시간/판정을 추출한다. 기존 PASS로부터 불일치가 없음을 추론한 값과 신규 직접 기록 mismatch 수를 구분한다.
- 9월 22일 PyTorch `comparisons/pair-*.json`을 8조건·144 tensor 항목의 정확성 표로 만든다. `atol=1e-6`, `rtol=1e-4`, 비유한 값·최대 절대/상대오차를 표시한다. 신규 runtime 검증으로 표기하지 않는다.
- 기존 snapshot 기반 타임라인은 `observed`로 표시하고, 신규 guest 계측 타임라인과 구분한다.

### 신규 실행

1. `guest_gpu_smoke.c`에 `copy_checked_bytes`, `copy_mismatches`, `kernel_checks`, `kernel_mismatches`, expected/actual 실패 예시, workload start/end를 추가한다. PTX와 입력 패턴은 기존 조건을 유지한다.
2. C3-S 5회를 먼저 실행해 계측 후 경로를 확인한다. 4096 B 왕복 복사, 4 B 정수 결과 `seed+i+19`, 매 반복 동기화·출력 검사를 수행한다.
3. C3-P는 두 VM 준비 완료 후 barrier로 출발한다. workload 시작은 첫 커널 직전, 끝은 마지막 결과 회수·검사 뒤로 정의한다. 부팅·ChannelReady·drain과 구분한다.
4. 두 Worker의 GPU PID/cgroup과 UUID를 동시 관측한다. 각 45초·5 pair를 수행하고 시각 오차를 고려한 공통 구간을 계산한다.

**실제 화면:** 분할 터미널에서 A/B 실행 명령→start→검사 수·mismatch 0→end·exit code를 보인다. 옆 터미널은 동일 GPU의 두 PID와 Worker 매핑을 표시한다.
**Grafana:** A/B active 상태 타임라인, GPU 전체 이용률, Worker별 메모리, 완료 작업 수·검사 수/불일치 수를 배치한다. start/end annotation을 표시하고 정밀 겹침 값은 clock 보정된 이벤트 원본에서 계산한다.
**캡처 장면:** 양쪽 실행 직후 / 동시 실행 중 / 양쪽 정확성 결과 / Released. 대표 pair는 시작 전부터 회수까지 연속 녹화한다.
**보조 자료:** 기능별 정확성 표, A/B start–end와 오차 범위·겹침을 표시한 정적 타임라인.
**판정:** 각 VM mismatch 0, API 성공, GPU UUID 일치, 독립 식별자, 보수적 겹침 ≥40초. 단독 정확성과 공유 성립을 각각 판정한다.
**산출물:** `correctness.csv`, `guest-events.jsonl`, `clock-map.json`, `overlap.csv`, 터미널 원본·타이밍, `sharing.webm`, 장면별 terminal/Grafana PNG·capture manifest, dashboard JSON·query 결과, 보조 SVG.

## ④ 메모리 한도 및 회수·재할당: C4

### C4-M: 1 GiB / 4 GiB 단계별 관측

각 한도에서 5회. 초기화 직후 `cudaMemGetInfo`의 total과 free를 기록하고, 성공 요청량 `R=floor(initial_free/2)`를 실행별 고정한다.

1. baseline 15초 → R 할당·15초 유지 → 기존 할당 유지 중 quota+1 B 추가 요청·예상 OOM 상태 15초 유지.
2. R 해제·15초 → R 재할당·15초 → 최종 해제·15초. 각 단계에 요청량·반환 코드·누적 성공 bytes·조회 free/total·이벤트 시각을 기록한다.
3. 같은 반복의 별도 boundary 단계에서 조회 잔여량 F 할당 성공→해제, F+1 B 거절, 잔여량 절반 재할당→해제를 검증한다. wrapper 반올림 단위와 내부 예약량을 기록한다. F는 물리 VRAM 전체가 아니다.
4. 앱 측 누적 할당량은 0으로, quota total/free는 초기값으로 복원되는지 확인한다. HAMi/프로세스 값은 관측 지연과 context 기준선을 따로 보고한다. monitor 복원 관측은 최대 30초 대기하고 미복원·timeout도 결과로 남긴다.

**실제 화면:** 터미널에 stage·요청 bytes·누적 성공량·CUDA 반환값을 출력한다. OOM code 2가 예상 결과임을 명시하고 해제·재할당까지 연속 기록한다.
**Grafana:** 한도 수평선 + 앱 성공 할당량 + HAMi/Worker process 사용량; GPU 전체 사용량은 별도 패널. allocate/OOM/free/reallocate annotation을 표시하고 실패 요청량을 실제 할당량에 더하지 않는다.
**캡처 장면:** 한도별 baseline / allocated / OOM / freed / reallocated. 발표에는 핵심 3~4장, 전체 단계는 원본 영상·캡처로 보존한다.
**산출물:** `memory-events.jsonl/csv`, `memory-samples.csv`, 한도별 terminal+Grafana PNG·연속 영상, dashboard/query 원본, 보조 메모리 SVG.

### C4-X: 한 세션 해제 후 다른 세션 재사용

4 GiB quota에 2세션을 미리 초기화한다. 먼저 각 세션이 단독으로 R=2,576,980,377 B를 할당·해제할 수 있는지 확인한다.
둘 중 하나라도 단독 R 할당에 실패하면 두 세션 합산 제한을 입증하는 시험으로 진행하지 않는다.

1. A가 R 할당·15초 유지한다.
2. B가 R 요청해 OOM을 받는다. A가 여전히 R을 보유하고 있음을 기록하고 15초 유지한다.
3. A가 해제 완료를 알린다. **B의 프로세스·세션을 재시작하지 않고** B가 같은 R을 재요청해 성공하는지 확인하고 15초 유지한다.
4. B 해제 후 양쪽 종료, 앱·HAMi 계상과 정상 회수를 확인한다.
5. A/B 역할을 바꿔 수행한다. 방향별 5회, 총 10회. 기존 동시 race 결과는 별도 표로 유지한다.

**판정:** 후행 요청 OOM, 선행 해제 후 후행 동일 세션 재요청 성공, 정해진 한도 내 계상·정상 회수.
Worker 프로세스에 세션이 합쳐지므로 프로세스 메모리로 세션별 실측을 주장하지 않는다. 세션별 성공 bytes는 앱 이벤트 장부로 표시하고 Worker 전체 계상과 대조한다.
**실제 화면:** 두 slot의 로그를 분할해 `A allocate OK → B OOM → A free OK → 동일 B session allocate OK`가 연속해서 보이게 한다. 방향을 바꾼 실행도 별도 기록한다.
**Grafana:** 세션별 앱 성공 할당량 누적 면적 + 4 GiB 한도선, Worker 전체 계상, OOM/free/retry annotation. A/B session ID와 run ID를 화면에 고정한다.
**캡처 장면:** 후행 세션 OOM / 선행 세션 free / 후행 동일 세션 재할당 성공. 방향별 원본 영상과 A→B/B→A 결과표를 보존한다.
**산출물:** `session-handoff-events.jsonl`, `aggregate-results.csv`, 방향별 terminal·Grafana PNG/영상, query 결과, 보조 `session-handoff.svg`.

정상 회수 20회 그래프는 기존 증거를 재사용한다. 런타임의 회수 로직을 수정하면 기존 결과를 새 버전의 근거로 승계하지 않고 해당 변경의 회귀 시험을 별도 수행한다.

## ⑤ 연산 설정값별 특성: C5

### 계측·부하·정책 준비

- `compute_probe.c`를 두 workload로 분리한다. grid 2048/block 256, thread당 FMA 반복은 긴 커널 1,048,576회와 짧은 커널 1,024회. 기존 긴 커널의 PTX·초깃값은 유지한다.
- native/guest에 같은 PTX·입력을 사용한다. 전체 524,288개 FP32 출력(2 MiB)을 **측정 구간 밖에서** 회수해 비교한다. 검산 D2H 시간을 커널 측정에 섞지 않는다.
- 같은 GPU에서 native 기준을 workload별 3회 실행해 출력 재현성을 확인하고 결과·hash를 고정한다. 후보 출력은 `abs(got-ref) <= 1e-6+1e-4*abs(ref)`, nonfinite 0 기준으로 검사한다. 기준 자체가 불안정하면 후보 성능 본 측정을 진행하지 않는다.
- `native-no-HAMi`와 `native-HAMi-limit-disabled`를 별도 대조 조건으로 준비한다. 후자는 지원되는 정책 해제 방법을 확인한 경우만 사용한다. compute 100을 자동으로 'limiter 없음'이라 부르지 않는다.
- 라이브러리 mapping/hash, 실제 환경변수·정책 switch, source/binary 대응을 모든 반복에서 수집한다. 정책 해제 대조가 불가능하면 그 비교를 미실행으로 표시한다.
- 포화도와 GPU clock/power를 대조 실행에서 관측한다. 짧은 커널의 호출 지연으로 포화도가 낮을 수 있으므로 장치 utilization만으로 limiter 효과를 판정하지 않는다.

### C5-T: 시간제 처리율·이용률

25/50/100 × 긴/짧은 커널 × 3회 = **18회**. 각 실행은 10초 준비 후 별도로 60초 이상 측정한다.
기존처럼 전체 시간에서 준비 시간을 빼지 않고 측정 시작 시점을 기준으로 종료한다.
마지막 커널 동기화 완료까지 실제 elapsed를 기록하며, `완료 커널 수/실제 elapsed`로 처리율을 구한다.
collector는 측정 구간과 정확히 겹치는 표본을 선택하고, 평균 이용률은 실제 간격을 반영한 시간 가중 평균과 원본 시계열을 함께 제공한다.

### C5-N: 동일 작업량 완료시간

workload별 compute 100 calibration에서 최소 30초가 되도록 커널 수 N을 선택하고 모든 설정에서 같은 N을 사용한다.
25/50/100 × 2 workload × 5회 = **30회**. timeout은 최저 설정의 예비 관측을 포함해 사전 확정한다.
한 workload의 반복 도중 N을 변경하지 않는다. 마지막 동기화까지 경과시간과 정확성을 기록한다.

**판정과 표현:** 정확성/실행/유효성은 별도 PASS/FAIL. limiter는 사전 정책 계약 충족 시만 판정한다.
정책 계약이 없으면 `NOT_EVALUATED`로 표시하되 '설정값별 관측 특성' 결과는 제시할 수 있다.
측정 결과가 같으면 차이가 관측되지 않았다고 보고하고 실패 원인을 workload 전체나 HAMi 전체로 일반화하지 않는다.

**실제 화면:** 터미널에서 compute 설정·grid/block·FMA 반복·N/측정시간을 확인하고 명령 실행, warm-up 종료, 완료 커널 수·elapsed·정확성 검산·exit code까지 표시한다.
**Grafana:** 설정값 25/50/100별 실제 시간 구간과 annotation, GPU 이용률·HAMi raw 지표, 완료 작업 counter·참고 처리율, 종료 결과 비교 패널을 둔다. 설정 50을 실제 이용률 50%로 표시하지 않는다.
**캡처 장면:** 각 설정 측정 중 화면 1장과 세 설정 완료 후 절대 시간 구간을 고정한 비교 화면. 대표 workload의 설정 전환 실행은 연속 기록하되 각 run ID를 구분한다.
**보조 자료:** workload별 시계열, 처리율 반복점·평균·표준편차, 고정 N 완료시간, 오차표. 최종 통계는 완료 결과 원본에서 계산하고 Grafana의 순간 rate와 구분한다.
**산출물:** `reference-output`와 hash, `compute-events.jsonl`, `compute-runs.csv`, `compute-samples.csv`, `correctness.csv`, `policy-contract.json`, terminal/Grafana PNG·영상·query 결과, 보조 SVG/PDF.
기존 9회 결과는 별도 '2026-09-24 관측' 패널로 재가공하고 신규 계측 결과와 합산하지 않는다.

## ⑥ 실행 오버헤드 및 공유 간섭: C6

### 공통 benchmark

기존 smoke만으로 호출비용과 연산비용을 대표하지 않도록 공통 CUDA benchmark를 준비한다.
직접 Driver API로 allocation/copy/launch/synchronize/free를 수행하고, guest에서는 같은 연산 경로를 shim으로 연결한다.
동일 PTX·입력·버퍼 크기·연산량을 사용하며 guest 전용 ABI 등록은 초기화 구간으로 분리한다.

- 입력/출력 버퍼는 각각 2 MiB. 결정적 정수 변환 커널을 사용해 기대값과 전수 비교한다. 커널 내부 반복 수는 calibration에서 하나로 동결한다.
- `resident`: 입력 1회 업로드 후 N회 kernel+sync, 마지막 출력 회수·검사는 측정 밖.
- `transfer`: 매 iteration 2 MiB H2D→kernel→sync→2 MiB D2H 완료까지 측정. 출력 검사는 측정 밖에서 수행하며 측정 중 정확성을 검증한 것처럼 표기하지 않는다.
- 본 측정 전 정확성 전용 실행으로 모든 iteration 결과를 검증한다. 본 측정은 마지막 출력도 확인한다. 두 실행의 프로그램·입력·N·연산 설정 일치를 검증한다.

### C6-A: host 직접 실행 대비 VM 경로

**주 비교:** 같은 GPU에서 `host native + HAMi` 대 `VM SHM + Worker + HAMi`.
기본 정책은 memory 4 GiB·compute 100·1세션이며 동일 libvgpu/설정으로 맞춘다. 제한 해제 조건을 쓰면 양쪽 모두 검증된 같은 방법을 적용한다.
native+HAMi baseline은 동일 런타임의 host-side 컨테이너에서 실행하고 컨테이너 사용 사실을 표에 명시한다.

guest vCPU backing에 대응하는 8개 host CPU를 native workload에 배정하고, Worker의 별도 4 CPU는 native 조건에서 다른 부하에 쓰지 않는다.
Worker 추가 CPU 사용량은 제안 경로의 비용으로 보고한다. 이 비교는 VM·shim·SHM·Worker를 포함한 **전체 경로 증가율**이며 순수 SHM 비용으로 단정하지 않는다.

resident/transfer별 N을 calibration에서 고정하고 최소 30초의 workload를 각 방식에서 독립 5회 실행한다.
2방식 × 2mode × 5회 = **20회**. 각 paired block에서 방식 순서를 교차한다.
`(VM elapsed / native elapsed − 1) × 100`을 paired 반복별 계산하고 평균·변동 범위를 표시한다.
unrestricted native를 추가하면 별도 참고 조건으로 분리하고 정책이 다른 결과로 순수 중계 비용을 계산하지 않는다.

호출별 상세 trace는 선택 항목이다. malloc/free, H2D/D2H, launch 반환, sync 완료를 구분하며 API 합계가 전체 elapsed와 일치한다고 가정하지 않는다.
**실제 화면:** native와 VM 각각의 실행 명령·동일 입력/작업량·정책, 완료시간·정확성 결과를 보존한다. 순차 비교임을 화면에 명시한다.
**Grafana:** backend별 실행 구간·GPU 이용률·CPU 비용과 완료 run별 elapsed/throughput 표를 표시한다. 성능 본 측정의 저장 구간을 사후 조회해 캡처하고 별도 시연 영상과 run ID를 섞지 않는다.
**보조 자료:** mode별 elapsed 반복점·평균, 증가율, guest/Worker CPU 비용.
**산출물:** `overhead-runs.csv`, `cpu-placement.json`, `cpu-samples.csv`, native/VM terminal 기록, 본 측정 Grafana PNG·query 결과, 별도 대표 시연 영상, 보조 SVG.

### C6-B: 두 VM 공유 간섭

모든 조건에서 VM별 4 GiB·compute 50·1세션과 동일 CPU 집합을 유지한다.
A seed 2026, B seed 2027의 고정 fixture를 사용한다. 각 VM의 단독과 동시 조건에서 자신의 fixture는 동일하다.

resident/transfer별 A 단독, B 단독, A+B 동시를 각 5회 실행한다.
2mode × 3조건 × 5회 = **30회**의 실행 묶음이며 A+B 한 묶음에는 VM 2대가 포함된다.
두 VM을 준비 실행시킨 뒤 공통 barrier로 시작하고 **90초** 실행한다.
시작 후 15–75초의 공통 60초를 사전에 측정 창으로 고정한다. 단독 조건에도 같은 창을 적용한다.
이벤트의 시각 오차를 고려해 양쪽이 해당 창 전체에서 실행 중이었는지 확인한다. 충족하지 못하면 측정 무효로 보존한다.

완료 작업을 chunk별 시작/끝·작업 수와 함께 기록한다. 예비 실행에서 chunk 경계 오차가 측정 창의 1% 미만이 되도록 크기를 고정한다.
공통 창 안에 완전히 포함된 chunk만 합산하고 경계에서 제외된 작업량을 함께 보고한다.
매 커널 파일 출력은 하지 않으며, 메모리 내 계수 후 제한된 chunk 이벤트로 계측 부하를 줄인다.

- VM별 throughput retention = `동시 처리율/자신의 단독 처리율`.
- VM별 slowdown = `자신의 단독 처리율/동시 처리율`로 정의하고 처리율 기반임을 표시한다.
- 동시 전체 처리율 = 공통 창의 `A+B 완료 작업 수 / 60초`.
- C3의 정확성 smoke와 달리 90초 성능 workload이다. 결과 검증·자원 조건·정상 회수도 함께 판정한다.

**실제 화면:** A 단독/B 단독/A+B 각각의 명령·동일 설정·결과를 남긴다. 동시 시연은 A/B 터미널을 분할하고 공통 barrier·측정 창 시작/종료를 표시한다.
**Grafana:** 조건별 실행 구간, VM별 완료 작업 수·참고 처리율, GPU 전체 이용률, 공통 60초 measurement annotation, 완료 run별 retention/slowdown·전체 처리율 표를 표시한다.
**캡처 장면:** A 단독 / B 단독 / A+B 동시 / 전체 반복 완료 비교. 본 측정 화면은 사후 조회 구간을 명시하며 대표 시연은 별도로 녹화한다.
**산출물:** `interference-runs.csv`, `chunks.jsonl`, `common-window.json`, terminal 기록·대표 영상, Grafana PNG·query 결과, 보조 비교 SVG.
정해진 성능 향상을 PASS 조건으로 두지 않는다. 공정한 조건·정확성·측정 유효성이 확보되면 간섭이 큰 결과도 그대로 보고한다.

## 구현해야 할 계측과 산출물 구조

| 대상 | 변경·추가 내용 |
|---|---|
| `guest_gpu_smoke.c` | 직접 mismatch 수, UTC/monotonic 시작·종료 이벤트 |
| `memory_probe.cu` | 단계별 시각·누적 앱 할당 장부, OOM 유지 구간, A/B 교대·동일 세션 재시도, stage 수에 맞춘 alarm/timeout |
| `compute_probe.c` | 긴/짧은 부하, 시간제/고정 N 모드, 출력 회수·검산·분리된 측정 구간 |
| 신규 공통 CUDA benchmark | C6 native/guest 동일 workload, resident/transfer·chunk 이벤트 |
| `run-evidence-smoke.py` 및 후속 runner | 신규 scenario/인자, clock 대응, 90초+준비 실행·고정 N의 별도 timeout, 독립 반복·순서표 |
| 수집기·분석기 | 1초 목표 collector, 실제 간격, PID/cgroup별 집계, clock 오차·공통 구간·가중 평균 |
| 전용 exporter·Prometheus | guest/runner 이벤트 노출, 실제 HAMi/GPU 지표 map, campaign 한정 scrape, 종료 결과·신선도 |
| Grafana dashboard·annotation | 실행/공유·메모리·compute·비교 dashboard JSON, 원본 이벤트 annotation, run별 절대 구간·query export |
| 터미널·브라우저 기록 도구 | 분할 터미널 출력/타이밍, 터미널+Grafana 연속 화면 녹화, 장면별 캡처·run ID/timecode 연결 |
| 보조 분석 그림 | 환경/정확성 표, quota/OOM/세션 교대, 반복별 통계·오버헤드/간섭 요약 |

현재 runner에는 90초 상한과 제한된 scenario가 있고 memory probe에도 100초 alarm이 있으므로 **기존 CLI로 위 신규 시험을 실행할 수 있다고 가정하지 않는다**.
위 변경을 구현하고 작은 입력·단일 실행으로 출력 검산과 이벤트 순서·정상 회수를 확인한 뒤 본 측정을 시작한다.
메모리 계측 변경만으로 runtime limiter 의미를 바꾸지 않는다. runtime 수정이 필요하면 별도 버전으로 정확성·회수 회귀를 먼저 검증한다.

예정 결과 구조는 다음과 같다. 아직 생성된 실험 결과가 아니다.

```text
results/<campaign-id>/
  protocol/       # campaign, conditions, run-order, policy-contract
  environment/    # versions, CPU/NUMA, placement, artifact hashes
  calibration/    # 본 측정에서 제외한 예비 결과
  runs/<run-id>/  # manifest, events, stdout/stderr, metrics, cleanup
  samples/        # GPU/HAMi/CPU, clock-map, PID/cgroup
  monitoring/     # Prometheus 설정·metric-map, Grafana dashboard JSON·annotation
  queries/        # 절대 from/to와 query, 실제 응답 JSON/CSV
  terminal/       # 실제 명령 stdout/stderr, 터미널 출력·타이밍/cast
  tables/         # correctness, memory, compute, overhead, interference CSV
  figures/        # 보조 SVG/PDF, 원본 경로·필터가 있는 figure manifest
  screenshots/    # terminal/Grafana PNG, capture manifest·연결된 원본
  video/          # 연속 원본 영상, 발표용 발췌, run ID별 timecode
  report.md
  SHA256SUMS
```

각 화면·그림에는 제목·축·단위·n·오차 표시 의미·날짜/버전·측정 범위를 적는다.
발표는 실제 터미널 명령·결과와 Grafana 실측 화면을 우선하고, 정적 통계 그래프는 반복 결과 설명을 보조한다.
실시간 시연, 실제 측정의 사후 조회, 기존 데이터 재가공을 구분하고 모두 원본에 연결한다.
학습 tensor·전체 private 환경을 공개할 필요 없이, 검토에 필요한 allowlist 결과·hash·조건을 저장한다.

기존 로그 가공과 문서·그림 작성은 바로 착수할 수 있다. 신규 GPU 실행은 공통 계측·정책/배치 확인을 마친 뒤 C3→C4→C5→C6 순서로 진행한다.
이번 계획은 기존 RPC/MPS·passthrough 세 방식 학습 성능 비교를 완료했다고 간주하지 않으며, 그 확장 실험은 별도 범위로 유지한다.
