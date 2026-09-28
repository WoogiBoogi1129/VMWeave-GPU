# 본 실험 이전 개발 트랙

> **오버헤드 비교의 현재까지 결과 공개 · 2026-09-29:** [호스트 직접+HAMi / Flyt TCP+MPS / 제안 SHM+HAMi](results/2026-09-29-overhead/README.md) · [발표 배치안](results/2026-09-29-overhead/PRESENTATION_GUIDE.md).
> 유효 63개 구간의 원본 표본·전체 정수 출력·CPU/정책 검증을 통과했다. 준비 실패와 조회 비교 1묶음의 제외·대체 기록도 보존한다. 녹화 없이 실제 터미널·Grafana PNG, 분석 그래프, CSV/XZ, Prometheus TSDB를 제공한다. 사용자 요청으로 확장 반복을 중단했으며 N 추가 6개 구간은 별도 보존한다. 6회 반복 계획 전체의 완료를 뜻하지 않는다. 현재 구현의 전체 경로 비교이며 전송 매체만의 효과 또는 전체 개발 gate 완료를 뜻하지 않는다.

> **3단계 완료 · 2026-09-29:** [두 VM의 동일 GPU 공유·서로 다른 메모리 한도](results/2026-09-29-stage3/README.md) · [발표 배치안](results/2026-09-29-stage3/PRESENTATION_GUIDE.md).
> 독립 VM 쌍 3/3 PASS. A(1 GiB)의 1536 MiB 요청은 OOM, B(4 GiB)는 성공했다. A의 같은 세션에서 128 MiB 후속 할당·검산, B의 기존 할당·검산 지속 및 양쪽 정상 회수를 확인했다. **녹화 없이 터미널 6장·Grafana 6장**, 원본 로그·CSV·실측 시계열·앞/뒤 출력 표본을 제공한다.

> **2단계 재실험 · 최신 발표용 자료:** [실제 로그와 정적 터미널 캡처](results/2026-09-28-stage2-static/README.md) · [발표 배치안](results/2026-09-28-stage2-static/PRESENTATION_GUIDE.md).
> 2026-09-28–29 KST에 새 VM 대표 실행 1회 PASS: 18개 요청·72개 추적 레코드 대응, 정수 262,144개 불일치 0, 정상 회수. **녹화 없이 PNG 7장·원본 로그·CSV·실제 출력 데이터**를 제공한다. 화면은 실험 후 bash/tmux/ttyd에서 실제 수집 로그를 조회한 캡처다. 이전 3회 결과와 구분하며 자체 뷰어 대신 이 자료를 사용한다.

> **발표용 시각 자료 수정:** [1단계 실제 터미널 시연](results/2026-09-28-stage1-terminal/README.md).
> bash에서 실행한 kubectl·SSH·nvidia-smi 명령과 출력을 asciinema로 녹화했다. 기존 자체 뷰어 대신 단계별 터미널 캡처와 원본 로그를 우선 사용한다.

> **2단계 실행 완료:** [SHM 요청·응답 추적과 계산 정확성](results/2026-09-28-stage2/README.md).
> 새 allocation 3회, 전체 54개 요청의 네 지점 trace 216행 대응, 매회 1 MiB·262,144개 정수 mismatch 0·free·Released를 확인했다. 기존 자체 뷰어 화면 19개와 영상 1개는 과거 보조 기록으로 보존한다. 추적 ON 기능 검증이며 성능·연산 제한 판정은 아니다.

> **1단계 실행 완료:** [GPU 요청–실제 배치·실행 연결 결과](results/2026-09-28-stage1/README.md).
> 새 allocation 3회에서 4 GiB·compute 50 전달, 실제 Worker GPU PID·HAMi 로드·동일 backing·BAR2 매핑과 정상 회수를 확인했다. 초기 준비 실패 1회는 별도 보존했다. 1단계 자체는 이용률 제한을 검증하지 않았으며 요청별 추적은 위 2단계에서 별도 수행했다.

> **발표자료 v3.0 기준 재설계:** [제안 항목별 구현·실험 계획](THESIS_V3_EXPERIMENT_PLAN.md).
> 요청–배치 연결, SHM 호출 왕복, VM별 메모리 한도, 연산 제한 진단을 중심으로 기존 시각 자료를 재사용한다. 1·2·3단계 완료 및 마지막 N/T/S 기본 3회 비교 공개, 연산 제한 등 나머지는 후속 계획이며 고정 작업량 완료시간 실험은 포함하지 않는다.
> 검토 반영: 단독/동시 공유 간섭 비교를 삭제하고, 마지막에 기존 FLYT TCP 경로 대비 SHM 호출·전송·처리율 오버헤드 비교를 추가했다.

> **2026-09-28 중단 후 자료 정리:** [확보된 시각 자료 목록](VISUAL_EVIDENCE_INVENTORY_2026-09-28.md).
> [공개 결과와 실제 화면](results/2026-09-28-campaign/README.md): 시간제 측정 18회, Grafana 캡처·영상, 원본에서 재생성한 그래프 및 기존 실험 시각 자료.
> 고정 작업량은 사용자 결정으로 중단했고 이번 공개에서 제외한다. 이 정리 당시 오버헤드·공유 간섭 비교는 미실행이었다. 오버헤드는 위 2026-09-29 결과로 기본 3회 결과를 공개했고 공유 간섭 비교는 현 계획에서 제외한다.

> 실제 후속 실행과 화면 증거: [2026-09-24 결과 보고서](IMPLEMENTATION_EXPERIMENT_RESULTS_2026-09-24.md).

> **2026-09-24 자료 제작 범위 변경:** [현재 구현·실험 계획](IMPLEMENTATION_EXPERIMENT_PLAN.md)을 따른다.
> 학습 정확성 비교와 장애 격리·복구 신규 실험은 제외한다. 아래 기존 전체 gate 및 과거 기록은 보존하며,
> 이번 시연·자원·정상 회수 결과를 E1~E5 전체 완료로 간주하지 않는다.
> D8 장애 fixture 및 신규 학습 정확성 비교는 이번 자료 수집의 실행 조건에서 제외한다.

현재 전체 선행 개발은 미완료다. 아래 표는 구현 과제와 종료 조건이며, 실제 통과 범위는 후속 보고서와 연결한다.

2026-09-22 후속 개발에서는 D1의 실제 VM 부팅·BAR·SHM 왕복과 D2의 두 VM
독립 GPU 실행을 확인했다. D4는 수동 보조 없이 정상 회수·신규 allocation 재사용
20회를 통과했다. 최종 controller v2b / Worker v3b에서도 별도로 20회를 다시 통과했다.
메모리 초과 후 세션이 닫히던 오류도 수정해 두 quota에서 재시험을 통과했다.
Worker Pod 강제 삭제 때 남던 재생성 Pod를 수정하고 새 버전에서 5회 재검증했다.
세부 실행 및 최종 판정은 [구현·검증 보고서](IMPLEMENTATION_AND_VALIDATION_2026-09-22.md)를 따른다.
후속 PyTorch 구현에서는 D3 대표 학습과 D5의 passthrough 기능 부분을 검증했다.
두 VM의 8개 학습 조건은 실제 passthrough와 1/100 step 결과가 모두 일치했다.
RPC·MPS, CPU/NUMA 통제, 연산 제한 계약은 남아 있어 전체 본 실험 진입은 아직 차단된다.
최신 판정은 [PyTorch 구현·검증 보고서](PYTORCH_IMPLEMENTATION_2026-09-22.md)를 따른다.

| ID | 구현·준비 작업 | 종료 조건/증거 |
|---|---|---|
| D1 | 현재 KubeVirt 1.9 launcher와 같은 배포판·QEMU 계열에서 ivshmem을 활성화한 QEMU/launcher 빌드. downstream 패치·module 경로·libvirt 동작 보존 | image digest, `-device help`의 ivshmem-plain, 기본 VM 부팅, hook domain XML, guest BAR, SHM 왕복 |
| D2 | 2개 VM의 독립 Channel/PVC/session, 지원 CUDA 복사·PTX kernel 실행 배포. guest/Worker image와 GPU UUID 연결 | 양쪽 Mapped 및 Channel Ready, 서로 다른 입력의 실제 GPU 결과, native GPU 우회 없음 |
| D3 | MLP 실행 시 필요한 Runtime registration/launch·라이브러리 API를 추적하고 지원. `cudaLaunchKernel`·fatbinary·packed 인자와 필수 entry 구현(대표 경로 PASS) | 같은 PyTorch 빌드에서 forward/backward/SGD, 1/100 step 결과, 지원 API와 변경 목록 |
| D4 | 정상 종료 시 launcher terminal/Worker exit 증거를 관측·보존하도록 수명주기 개선 | 테스트용 finalizer 없이 일반 종료·Released·backing 삭제·신규 allocation 재사용. 이전 세대 재사용 금지 |
| D5 | GPU 1의 IOMMU/VFIO 전환·원복, passthrough VM과 보존 RPC/MPS baseline 구성 | 같은 UUID/guest/PyTorch/CPU·NUMA 조건, baseline 자체 반복 정확성, GPU 중복 소유 없음 |
| D6 | VM당 8 vCPU/16 GiB, Worker당 4 CPU 초기 예산에 대한 실제 배치 및 계측·회수 어댑터 | immutable image IDs, guest/host CPU 집합, 서로 겹치지 않는 cgroup 경로, guest 실행/취소/결과 회수 명령 |
| D7 | 설치 libvgpu v2.10.0 바이너리와 일치하는 소스·컴파일 설정을 확보하고 quota 계약 확정 | 메모리 내부 예약량·다중 프로세스 계상 범위·경계 값; 연산 limiter 대상/구간/허용오차와 관측 도구 |
| D8 | 격리 장애 fixture 및 제어기 복구 어댑터 구성 | VM A의 각 장애 주입·원상복구, VM B의 정확성/연속 실행, 회수 보류와 완료의 독립 판정 |

GPU 1은 2026-09-22 점검에서 NUMA 0, BDF `0000:41:00.0`, IOMMU 그룹 26에
단독 장치로 관측됐다. 후속 PyTorch 검증에서 HAMi 제외를 실제 probe로 확인한 후 VFIO 전환,
passthrough VM 학습, NVIDIA 원복과 HAMi 4개 GPU 재등록까지 수행했다.
다음 전환에서도 HAMi 등록/예약과 실제 GPU 사용을 새로 확인해야 한다.

이전 설치 보고서의 시험용 finalizer 보조 성공을 D4 통과로 승계하지 않는다.
기존 Draining 채널 a는 그대로 보존하고, 새 allocation으로 검증한다.
Pod 부재·Node NotReady·API 접근 실패는 detach 완료의 근거가 아니다.

전체 개발 종료 후 새 디렉터리에 preflight를 수행하고, 실제 증거 파일과 해시를
각 gate에 연결한다. correctness gate는 E1 결과로, calibration gate는 전체 방식의
예비 실행으로 채운다. 개발 버전의 성능값을 본 실험에 편입하지 않는다.

실제 노드 단절은 외부 관측·복구 및 유지보수 범위를 별도로 확보할 때 수행한다.
다중 GPU는 2개 물리 장치의 실행/매핑/부분 실패/회수가 구현된 뒤 별도로 수행한다.
