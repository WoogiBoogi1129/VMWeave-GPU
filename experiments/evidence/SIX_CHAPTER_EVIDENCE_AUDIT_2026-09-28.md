# 6장 구성에 대한 실험 근거·시각 자료 점검

점검일: 2026-09-28. 대상 저장소 HEAD: `75b5696`.
이번 작업은 기존 파일·원본 측정값·소스·그림의 검토이며, GPU 실험을 새로 실행하지 않았다.
9월 24일 SHM/HAMi 시연을 중심으로 9월 22일 PyTorch 검증과 과거 RPC/MPS 자료를 대조했다.
`results/2026-09-24-showcase/SHA256SUMS`의 418개 파일은 모두 해시가 일치했다.
해시 일치는 보존 상태 확인이며, 실험의 정확성이나 성능 판정을 대신하지 않는다.

**판정:** ③·④는 기존 근거를 상당 부분 활용할 수 있으나 시각 자료 보완이 필요하다.
⑤는 이용률과 커널 처리율 관측이 있으며, 정확성·고정 작업량 시간·제한 정책 검증은 추가 실험이 필요하다.
⑥의 공정한 오버헤드·공유 간섭 비교는 새로 측정해야 한다.

| 장 | 원본·조건의 확보 상태 | 시각 자료 상태 | 남은 작업 |
|---|---|---|---|
| ① 구현 환경·구성 | 환경 JSON, VM/Worker/GPU 식별자, 이미지·소스 해시 있음 | 환경 정보는 문서에 분산. 기존 독립 SVG 배치도는 RPC/MPS 구조 | 현재 SHM/HAMi 배치도와 통합 환경 표, CPU 모델·소켓·코어 원본 보존 |
| ② 검증 항목·조건 | 실행 소스·manifest·설정 있음 | 요청한 목적–조건–판정 기준 통합 표 없음 | 아래 표를 기반으로 실험별 버전·반복·측정 구간 확정 |
| ③ 정확성·공유 | 정수 smoke, FP32 tensor 비교, 같은 GPU의 두 Worker 관측 있음 | 실제 화면·영상 있음. 기능별 수치 표와 A/B 실행 타임라인 없음 | 기존 결과 표 작성, 관측 타임라인 제작. 정확한 실행 시작·종료 시각은 계측 보강 후 재실행 |
| ④ 메모리·회수 | 1/4 GiB OOM·복구, 4 GiB 합산 거절, 정상 회수 20회 있음 | 메모리·회수 그래프 있음. 한도선·OOM 표시·합산 그림 부족 | 기존 그래프 보완, 세션 간 해제 후 재할당 실험 추가 |
| ⑤ 연산 설정 | 25/50/100 각 3회 이용률·launch 수·측정시간 있음 | 평균 이용률 산점도 있음. 시계열·처리율·고정 작업량 시간 그림 없음 | 기존 로그 재가공 + 결과 검산·고정 작업량·limiter 대조 시험 |
| ⑥ 오버헤드·간섭 | 과거 진단 시간은 있으나 동일 조건의 정식 비교 없음 | 적합한 비교 그림 없음 | host direct/VM, A 단독/B 단독/A+B 비교 신규 실행 |

아래 경로에서 `S`는 [9월 24일 공개 결과](results/2026-09-24-showcase/),
`P`는 [9월 22일 PyTorch 결과](results/2026-09-22-pytorch/)를 뜻한다.
표나 그림이 없거나 필요한 주장을 충분히 보여 주지 못하면 자료가 있어도 **보완 필요**로 판정했다.

## ① 구현 환경 및 실험 구성

**확보한 근거**

- [S/environment.json](results/2026-09-24-showcase/environment.json): 노드 `gpu-4`, GPU 4개의 모델·UUID·메모리, 드라이버, kubelet·CRI-O, 호스트 OS·커널, 실행 이미지.
- [PyTorch 환경](PYTORCH_IMPLEMENTATION_2026-09-22.md): guest Ubuntu 22.04.5 / kernel 5.15.0-191-generic, VM당 8 vCPU·16 GiB RAM·16 GiB root, CUDA 12.8, PyTorch `2.11.0+flyt.cu128`.
- [설치 기록](../../docs/installation/INSTALLATION_REPORT_2026-09-22.md): KubeVirt 1.9.0, HAMi 2.10.0. 초기 SHM 미완료 판정은 후속 결과와 구분한다.
- [후속 구현 기록](IMPLEMENTATION_AND_VALIDATION_2026-09-22.md): QEMU 10.1.0-20.el9 소스 RPM 기반 ivshmem 활성화 빌드.
- [S/compute-protocol.json](results/2026-09-24-showcase/compute-protocol.json): HAMi-core `b216ba1be1b8e21488d1c7370ed3357b3049aad1`, 설치 libvgpu 해시.
- `S/runs/evidence-show-capture-{a,b}/run/identity.json`: 서로 다른 VM UID·Worker UID·allocation, 동일 GPU UUID, 각각 4096 MiB·compute 50.
- [S/gpu-process-worker-map.json](results/2026-09-24-showcase/gpu-process-worker-map.json), `process-cgroups.jsonl.gz`: host PID → cgroup → Worker UID 연결.
- [S/images.json](results/2026-09-24-showcase/images.json), [S/source-artifact-hashes.json](results/2026-09-24-showcase/source-artifact-hashes.json), `runs/*/run/program-hashes.json`: 실행 버전 식별. 실행 기준은 `2912677` + 미커밋 파일 해시이며, 현재 HEAD와 동일하다고 표기하지 않는다.

실험 GPU는 `GPU-7d708c42-8d4a-16d5-0746-474567157aa3`, BDF `0000:41:00.0`이다.
장착 GPU 4개 중 이 1개를 사용한다. 기본 시험은 1 VM, 공유 시험은 2 VM이다.
공유 시험 경로는 VM A → 독립 SHM Channel/PVC A → Worker A와 VM B → 독립 SHM Channel/PVC B → Worker B가 같은 물리 GPU에 연결되는 구조다.

**보완할 자료**

- [기존 SVG](../../docs/flyt-k8s-track-a2-architecture.svg)와 [ARCHITECTURE.md](../../docs/ARCHITECTURE.md)는 DRA/RPC/MPS 경로이므로 현재 배치도에 그대로 사용하면 안 된다. 현재 SHM/HAMi 도식은 별도 제작이 필요하다. 사용자 보유 배치도가 저장소 외부에 있다면 이번 확인 범위에 포함되지 않는다.
- 환경 표에 CPU 모델·2소켓·64물리코어·128스레드와 RAM을 합친다. 앞선 서버 조회값은 현재 관측이며, 9월 24일 당시 CPU 토폴로지 원본으로 소급하지 않는다. `lscpu`, `free -b`, 수집 시각을 파일로 보존하면 재현 조건 자료가 된다.
- Kubernetes v1.37.0은 환경 JSON의 kubelet 보고값이다. API server 버전까지 명시하려면 별도 `kubectl version -o json`이 필요하다.
- 1세션 SHM backing 64 MiB, 2세션 128 MiB는 [layout 생성 코드](../../runtime/shm/control/provision.py)에서 계산된다. 재실행 때 실제 backing 크기·BAR 크기·세션 수도 manifest에 저장한다.
- 환경 장에는 위 조건 표와 배치도만 넣고, PASS 수·측정시간·실행 화면은 넣지 않는다.

## ② 검증 항목 및 실험 조건

다음 표는 기존 실행의 조건과 아직 확정하지 못한 조건을 구분한 것이다.

| 검증 목적 | 실행 조건과 근거 | 판정 기준·미확정 사항 |
|---|---|---|
| CUDA 정수 기능·정확성 | [guest_gpu_smoke.c](guest_gpu_smoke.c): 4096 B 패턴 H2D/D2H, 4 B 정수 결과, PTX `write_value`, grid 1/block 1, `seed+i+19` 기대값 | 복사 `memcmp` 일치, 매 커널 결과의 정확한 정수 일치, API 반환 성공. 첫 불일치에서 종료하며 별도 mismatch count 필드는 없음 |
| FP32 정확성 기존 근거 | MLP 1024→2048→1024, FP32 SGD; batch 32/1024 × resident/transfer × seed 2026/2027; step 1/100의 loss·gradient·parameter | `abs(got-ref) <= 1e-6 + 1e-4*abs(ref)`, nonfinite·누락 없음. 9월 22일 제한된 경로 검증 |
| 두 VM 공유 | 각 4 GiB·compute 50·1세션, 서로 다른 seed, barrier 이후 각 45초. 최초 pair + host PID 관측 보강 pair | 같은 GPU UUID, 다른 Worker/PVC/Channel, 실제 동시 프로세스 관측, 양쪽 결과 일치·정상 완료 |
| 메모리 제한·복구 | 1/4 GiB 각각 `observe`와 `suite`. 초기 조회 잔여량의 절반 1회 할당, 해제 후 동일량 재할당. baseline/allocated/freed/reallocated 각각 15초 | quota+1 요청 OOM, 재할당 성공, 최종 조회 잔여량 복원. 별도 suite는 조회 잔여량 경계/경계+1 시험 |
| 두 세션 합산 | 한 Worker·2세션·4 GiB 합산 한도·compute 100; 각각 2,576,980,377 B 동시 요청 | 정확히 한 세션 성공/한 세션 OOM. 둘 다 OOM이면 입증 불충분. 해제 뒤 상대 세션 재시도는 미실행 |
| 연산 설정 관측 | 4 GiB·1세션, compute 25/50/100, 각 3회 새 VM, 순서 교차. grid 2048/block 256, thread당 종속 FMA 1,048,576회; 준비 실행 약 10초 + 측정 약 61초 | 현재는 실행 완료 판정만 있음. 제한 오차·시간 구간·정책 계약은 `NOT_ESTABLISHED`. 계산 결과 검산 없음 |
| 오버헤드·간섭 | 동일 입력·작업량·GPU·자원 정책·CPU/NUMA를 고정한 비교 필요 | 현재 미실행. 독립 5회, 준비 실행과 공통 측정 구간 고정을 신규 계획으로 제안 |

조건 근거는 [실행 스크립트](../../scripts/run-evidence-showcase.py), [메모리 probe](memory_probe.cu),
[compute probe](compute_probe.c), [기존 전체 계획 config](config.json)이다.
`config.json`의 90초 공유·60초 공통 구간·50 warm-up step·성능 5회는 원래 계획이다.
9월 24일의 실제 45초 smoke·10초 compute warm-up·3회 반복과 섞지 않는다.
smoke와 메모리 시험에는 compute와 같은 별도 10초 warm-up이 없다.

수집기는 [serve-evidence-dashboard.py](../../scripts/serve-evidence-dashboard.py)에서 조회를 마친 후 2초 대기한다.
따라서 수집 간격은 고정 2초가 아니다. `S/plots/samples.csv`의 compute 측정 구간 9회에서
인접 표본 간격은 약 **2.634–2.866초, 중앙값 2.766초**였다.
브라우저 1.5초 갱신 간격과 실제 수집 간격을 구분한다.
GPU/HAMi/API 조회는 순차적이고, snapshot 시작·완료 시각 사이에도 지연이 있다.

## ③ CUDA 실행 정확성 및 GPU 공유

**원본과 실제 결과**

- `S/runs/evidence-show-{pair,capture}-{a,b}/run/`: `metrics.json`, `guest-stdout.txt`, `guest-command.json`, `identity.json`, `timeline.json`, `manifest.json`.
- 최초 pair: A 10,570회 / 45.003566초, B 10,713회 / 45.001709초, 양쪽 PASS.
- host PID를 관측한 capture pair: A 10,788회 / 45.000839초, B 10,681회 / 45.001403초, 양쪽 PASS.
- 이 4개 VM 실행은 모두 4096 B 복사와 매 커널 정수 비교를 통과했다. 불일치가 발생하면 종료하는 소스에 따른 **불일치 없음의 근거**는 있으나, 출력에 `mismatch_count: 0`이 직접 기록된 것은 아니다. kernel 반복 수를 독립 실험 반복 수로 세지 않는다.
- [P/comparisons](results/2026-09-22-pytorch/comparisons/): `pair-*.json` 8조건 × 18 tensor = 144개 비교 항목. 허용 오차 초과 0, 최대 절대오차 0, 0이 아닌 기준값에 대한 최대 상대오차 0. 이는 compute FMA probe 검증과 다른 시험이다.
- [P/README.md](results/2026-09-22-pytorch/README.md): 공개 저장소에는 tensor 비교 결과·해시를 보존하고 tensor 본체는 제외했다. `.local/pytorch-path-20260922`에는 일부 tensor 파일이 존재하나, 모든 공개 비교의 원본 세트가 복구 가능한지는 별도 해시 대조가 필요하다.

**확인한 시각 자료**

- [추가 두 VM 공유 화면](results/2026-09-24-showcase/screenshots/additional-two-vm-gpu-sharing.png): 동일 UUID, Worker A/B, GPU host PID 19127/24575, 서로 다른 seed의 명령을 확인할 수 있다.
- [실행 영상](results/2026-09-24-showcase/video/two-vm-live.webm): 파일 존재 확인. 영상 전체 프레임은 이번 점검에서 재검토하지 않았다.
- 기능별 정확성 수치표, FP32 오차표, A/B 45초 실행 타임라인은 별도 시각 산출물이 없다.

**보완 방향**

1. 기존 JSON으로 함수/입력/기대값/검사 수/오차/판정 표를 만든다. 정수 smoke와 PyTorch tensor 검증의 날짜·버전을 명시한다.
2. snapshot·PID/cgroup·Channel 타임라인으로 **관측된 동시 사용 구간** 그림은 제작 가능하다.
3. 정확한 GPU 작업 시작·끝 시각은 부족하다. `timeline.json`의 ChannelReady/ProbePassed는 host polling 관측 시각이며, `active_seconds`는 guest 경과시간이다. GPU 프로세스 존재 구간도 커널 실행 구간과 다르다. 이를 그대로 45초 정밀 타임라인으로 바꾸지 않는다.
4. 정밀 타임라인이 필요하면 guest의 workload start/end·monotonic clock, host 수신 시각·시계 대응, run ID, 결과 불일치 수를 기록하고 두 VM 시험을 다시 실행한다. 시계 오차·polling 오차를 함께 표시한다.

## ④ 메모리 한도 및 회수·재할당

**원본과 실제 결과**

`S/runs/evidence-show-mem-{1024,4096}-observe/run/metrics.json`과 `guest-stdout.txt`에 요청 bytes·CUDA 반환값·해제·재할당·계상 복원이 있다.

| 한도 | 실제 성공 할당·재할당 요청 | 추가 초과 요청 | 결과 | 조회 잔여량 복원 |
|---|---:|---:|---|---:|
| 1 GiB | 248,512,512 B | 1,073,741,825 B | OOM code 2 후 해제·재할당 PASS | 497,025,024 B → 동일 값 |
| 4 GiB | 1,859,125,248 B | 4,294,967,297 B | OOM code 2 후 해제·재할당 PASS | 3,718,250,496 B → 동일 값 |

초과 요청은 기존 할당을 유지한 상태에서 **한도+1 byte를 추가 요청**한 것이다.
누적량이 경계를 1 byte 넘는 시험과 구분한다. 후자는 별도 `suite`의 조회 잔여량 경계 시험으로 제시한다.
`mem-1024-suite`의 준비 실패와 `mem-1024-suite-retry`의 성공을 함께 보존한다.

- `S/runs/evidence-show-aggregate/run/metrics.json`: 각 2,576,980,377 B, 요청 합계 5,153,960,754 B > 4 GiB, 반환 `[0,2]`, PASS.
- 이는 **합산 요청 약 4.8 GiB 중 약 2.4 GiB만 성공**한 결과다. 실제 4.8 GiB가 할당됐다고 그리면 안 된다.
- [메모리 1 GiB 그림](results/2026-09-24-showcase/plots/memory-1024.png), [4 GiB 그림](results/2026-09-24-showcase/plots/memory-4096.png): 장치/프로세스/HAMi 사용량 시계열과 stage 표시 있음.
- [정상 회수 그림](results/2026-09-24-showcase/plots/lifecycle.png), `lifecycle-summary.json`, `final-audit.json`: 20/20 정상 회수·새 allocation 재사용. 메모리 `cudaFree`와 VM/Worker/PVC backing 수명주기 회수는 별도 지표다.

**부족한 시각 자료와 신규 시험**

- 기존 메모리 그림의 한도는 제목에만 있다. y축을 넓혀 1024/4096 MiB 한도선을 넣고, 앱의 성공 할당량과 실패한 추가 요청량·OOM 반환을 따로 표시해야 한다.
- `over_quota` 직후 `freed`가 출력돼 polling이 OOM 순간을 놓칠 수 있다. 원본 stdout에는 순서가 있으나 정확한 wall-clock 시각이 없다. 기존 그림에는 구간 주석으로 표시하고, 정확한 이벤트선이 필요하면 timestamp 출력 후 재수집한다.
- 합산 제한의 요청량/성공량/거절량 그림이 없다. 기존 로그로 정적 요청·결과 막대는 제작할 수 있다. 세션별 시간 변화 그래프에는 추가 계측이 필요하다.
- **A가 해제한 뒤 OOM을 받은 B가 같은 세션에서 재요청해 성공하는 시험은 없다.** `memory_probe.cu`의 race 자식은 1회 할당 후 해제·종료한다. 신규 순차 동기화 시험으로 채워야 한다.
- `plots/samples.csv`의 `gpu_process_memory_mib`는 수집된 GPU process 메모리의 합이다. [plot_showcase.py](plot_showcase.py)는 PID별 cgroup 필터 없이 같은 snapshot 값을 Ready VM 행마다 기록한다. 공유 시험에서 이를 VM별 메모리로 사용하지 말고 `process-cgroups.jsonl.gz`로 Worker별 재집계한다.
- HAMi 계상에는 context 예약량 등이 들어간다. 앱 할당량, Worker process 사용량, HAMi 계상, 물리 GPU 전체 사용량을 각각 표시한다.

## ⑤ 연산 설정값에 따른 실행 특성

**확보한 원본**

- `S/runs/evidence-show-compute-{25,50,100}-{1,2,3}/run/metrics.json`: warm-up 횟수, 측정 커널 횟수 `launches`, 실제 `measurement_seconds`, grid/block.
- [S/plots/samples.csv](results/2026-09-24-showcase/plots/samples.csv): UTC 시각, 실행 ID, 장치 이용률, HAMi 지표, 측정 시작 여부, 수집 오류 필드. 총 438행 중 수집 오류 표시 0행.
- `S/snapshots-host.jsonl.gz`, `compute-settings/`, `compute-libraries/`, `compute-protocol.json`: 원본 관측·설정·실제 library mapping. library mapping은 두 번째 반복부터 보존했다.
- [평균 이용률 그림](results/2026-09-24-showcase/plots/compute-observed.png)과 `compute-summary.json`: 9회 평균 장치 이용률 약 87.1–88.6%, 제한 판정 `NOT_EVALUATED`.

커널 뒤마다 `cuCtxSynchronize`하므로 `launches / measurement_seconds`로 **동기화 완료 커널/초**를 계산할 수 있다.
이번 점검에서 원본 9개 JSON으로 산출한 값이며, 새 실험 결과가 아니다.

| compute 설정 | 반복 1/2/3 커널 횟수 | 처리율 평균 (회/초) | 반복별 처리율 최소–최대 |
|---|---|---:|---:|
| 25 | 5119 / 5149 / 5118 | 84.079 | 83.906–84.409 |
| 50 | 5101 / 5156 / 5132 | 84.090 | 83.616–84.525 |
| 100 | 5129 / 5103 / 5089 | 83.720 | 83.424–84.084 |

각 측정은 약 61초다. 이 표는 GPU FLOPS나 학습 처리량이 아니며, 설정값에 비례한 제한의 성공을 뜻하지 않는다.

**보완할 시각 자료**

- CSV에서 warm-up·종료 후 표본을 제외해 설정별 이용률 시계열을 만든다. 장치 전체 이용률과 HAMi raw 지표의 축·단위를 구분한다.
- 위 원본으로 반복별 점 + 평균·변동 범위를 표시한 커널 처리율 그래프를 만든다. 현재 저장된 그림은 평균 이용률 산점도뿐이다.
- 실제 같은 작업량 완료시간 비교 그림은 만들 수 없다. 각 실행의 완료 커널 수가 다르므로 61초를 동일 작업량의 실행시간으로 해석하지 않는다.

**추가 실험이 필요한 부분**

- `compute_probe.c`는 FMA 결과를 device 메모리에 쓰지만 D2H 회수·기준값 비교를 하지 않는다. PASS는 API 호출·완료 성공이다. 25/50/100 각각의 계산 정확성은 결과 회수와 검산을 추가해야 한다.
- 고정 커널 수 N으로 동일 작업량을 실행하고 동기화 완료까지 시간을 기록한다. N은 calibration 후 고정하며 설정별 독립 반복을 수행한다.
- 현재 정책 계약과 설치 바이너리의 전체 빌드 옵션은 미확정이다. 실제 제한 관련 환경변수, libvgpu mapping/hash, 정책 switch, 정책의 대상 지표·관측 구간·허용오차를 기록한다.
- 같은 장치에서 native 또는 HAMi 비제한 대조 부하의 포화도를 확인하고, 기존 긴 FMA 커널과 짧은 반복 커널을 별도 조건으로 비교한다. 이를 통해 부하 특성과 제한 적용의 영향을 구분한다. 측정 전부터 25/50/100%를 달성해야 한다고 결론 내리지 않는다.

## ⑥ 실행 오버헤드 및 공유 간섭

[S/performance-readiness.json](results/2026-09-24-showcase/performance-readiness.json)은 `NOT_RUN`이다.
9월 22일 `P/*/metrics.json`에는 학습 elapsed/throughput 진단 값이 있지만, warm-up·calibration·독립 5회·CPU/NUMA 통제가 충족되지 않았다.
단일 SHM 시험은 compute 100, pair는 각각 50이고 controller 버전도 다르므로 그대로 공유 간섭률을 계산하면 안 된다.
과거 8월 [실험 보고서](../../docs/archive/2026-08-experiment-report.md)의 RPC/MPS·46/92 SM 결과는 현 SHM/HAMi의 baseline이 아니다.

**필요한 신규 비교**

| 비교 | 고정할 조건 | 기록할 값 | 시각 산출물 |
|---|---|---|---|
| host direct vs VM SHM 경로 | 동일 GPU UUID·프로그램·입력·작업량·CUDA; 비교에 맞는 CPU/NUMA 예산, GPU 메모리·연산 정책 동등화 | 반복별 workload 시작→최종 동기화 완료 시간, 정확성, host/guest/Worker CPU 비용 | 개별 반복점·평균·범위, `(VM/direct−1)×100` 증가율 |
| A 단독 / B 단독 / A+B 동시 | 모두 VM당 4 GiB·compute 50·1세션, 같은 Worker/guest image, 동일 입력 규모·작업량; 독립 입력은 seed만 구분 | VM별 처리율·시간·정확성, 동일 공통 구간의 전체 처리율 | VM별 단독/동시 막대·반복점, 합계 처리율 |

직접 실행이 비제한이고 VM에만 HAMi 제한이 걸리면 호출 중계만의 오버헤드로 해석할 수 없다.
그 경우 정책을 맞추거나 제한 정책 차이를 포함한 end-to-end 비교라고 범위를 명시한다.
VM 직접 passthrough baseline은 host direct와 다른 비교이므로 구분해 기록한다.
RPC/MPS 세 방식 비교는 원래 계획의 확장 항목이며, 위 두 비교를 위해 반드시 먼저 수행할 필요는 없다.

호출별 분석을 선택하면 malloc/free, H2D/D2H, kernel launch 반환, 동기화 완료를 분리한다.
VM 부팅·이미지 준비·드레인 시간은 workload 실행시간 분모에 섞지 않는다.
비동기 경로의 API 반환과 GPU 완료도 별도 측정한다.

## 추가 작업의 우선순위와 전달 자료

| 우선순위 | 작업 | 새 GPU 실행 | 완료 시 필요한 파일·그림 |
|---|---|---|---|
| P0 | 현 SHM 배치도·통합 환경 표·목적/조건/판정 표 | 불필요. 환경 원본 조회는 별도 | 버전/UUID/해시가 연결된 조건 문서, SVG/PDF |
| P0 | ③ 정수/FP32 정확성 수치표와 관측 기반 공유 타임라인 | 기존 범위는 불필요 | correctness.csv, overlap-observed.csv, 표·타임라인 그림 |
| P0 | ④ 1/4 GiB 그래프에 한도·실패 요청 주석, 합산 요청/성공량 그림 | 정적 보완은 불필요 | memory-events.csv, memory-{1024,4096}.svg, aggregate.svg |
| P0 | ⑤ 이용률 시계열·커널 처리율 반복 비교 | 불필요 | compute-runs.csv, compute-timeseries.svg, compute-throughput.svg |
| P1 | 정확한 시작/종료·OOM 시각과 mismatch 수 계측 | 정밀 시각 증거를 요구하면 필요 | guest event JSONL + host clock 대응, A/B 타임라인 |
| P1 | A 해제 후 B 재요청 성공, 역방향도 확인 | 필요 | slot별 요청/성공/해제/잔여량/시각 JSONL, 세션별 사용량 그림 |
| P1 | compute 결과 검산 + 고정 N 작업량 + 정책/포화 대조 | 필요 | 25/50/100 반복별 correctness·runtime·throughput CSV, 비교 그림 |
| P2 | ⑥ direct/VM 오버헤드와 단독/동시 간섭 | 필요 | baseline·각 VM별 반복 원본과 통합 CSV, 두 비교 그림 |

신규 반복 정책은 **제안**으로서 사전 고정한다: 성능·간섭은 독립 5회, compute 관측은 최소 기존과 같은 설정별 3회,
메모리 세션 교대는 A/B 역할을 바꾸어 반복한다. 준비 실행·본 측정 구간·순서 교차·실패 처리 규칙을 실행 전에 manifest에 기록한다.
기존 9월 24일의 39개 실행 중 38 PASS/1 준비 FAIL은 서로 다른 시험을 합친 수치이므로 서비스 성공률로 쓰지 않는다.
정상 회수 20회와 정확성 kernel 반복 수를 성능 독립 반복 수로 합산하지 않는다.

원본 전달 묶음에는 다음을 포함한다.

- 공통: run ID, UTC 시작·종료, monotonic duration, VM/Worker/Channel UID, GPU UUID, 이미지 digest·프로그램/입력 hash, quota·compute·session·SHM bytes, 준비 실행·측정 구간·반복 번호.
- 정확성: API/입력 bytes·기준식 또는 기준 tensor hash, 검사 원소 수, mismatch/초과 원소 수, 최대 절대·상대오차, 허용치, PASS/FAIL.
- 메모리: session slot, 이벤트 시각, 요청량·성공량·누적 앱 할당량·해제량·반환 코드·조회 잔여량, HAMi/프로세스/장치 관측값과 수집 시각.
- 성능: 완료 커널 수 또는 처리 샘플 수, 동기화 완료시간, 각 반복 처리율, 장치 이용률 표본, CPU/NUMA 설정과 실제 배치, 정책 적용 증거.
- 각 그림: 생성 코드·원본 CSV/JSON 경로·필터 기준·단위·시계 기준·오차 또는 표본 간격. 실제 화면은 PNG와 같은 snapshot JSON을 함께 제공한다.

이번 점검에서는 근거를 정리한 이 문서만 추가했다. 기존 원본·그림·실험 설정과 클러스터는 변경하지 않았다.
