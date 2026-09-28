# 2단계 — SHM CUDA 요청·응답 추적과 계산 정확성

> **표현 방식 수정:** 핵심 근거는 [Guest 원본 로그](runs/evidence-s2-0928-01/guest-stderr.txt),
> [Worker 원본 로그](runs/evidence-s2-0928-01/worker-stderr.txt), [계산 결과](runs/evidence-s2-0928-01/stdout.jsonl)다.
> 자체 뷰어 화면은 발표 기본 자료에서 제외하고 과거 보조 기록으로 보존한다. 이번 변경은 2단계 재실행이 아니다.

**2026-09-28 실제 실행: 독립 allocation 3/3 PASS.** 각 실행에서 CUDA 요청 10개를 포함한
18개 요청을 `Guest submit → Worker take → Worker respond → Guest receive`로 연결했다.
1 MiB 전체 262,144개 정수의 불일치는 매회 0개였으며 할당·H2D·커널·동기화·D2H·해제를 확인했다.
기존 1단계와 별도의 새 VM/Worker/채널/세션 3개를 사용했다.

| 회차 | Allocation | 전체 요청 / CUDA 요청 | 네 지점 trace 행 | 정수 검사 / 불일치 | 해제·회수 |
|---|---|---:|---:|---:|---|
| 1 | `644993260ad2999eb34227aab0fb2871` | 18 / 10 | 72 | 262,144 / 0 | PASS |
| 2 | `5213b9a44ee354782caa294e68c476c8` | 18 / 10 | 72 | 262,144 / 0 | PASS |
| 3 | `afeb82c2d93c262693cc32a14c0a6cfe` | 18 / 10 | 72 | 262,144 / 0 | PASS |

합계는 **54개 요청·216개 endpoint 레코드·CUDA 요청 30개·검사 정수 786,432개**다.
전체 요청에는 회차당 HELLO 1개·HEARTBEAT 6개·GOODBYE 1개가 포함된다.
`flytRegisterKernelABI`는 Guest 내부 메타데이터 등록이므로 원격 CUDA 요청 수에 포함하지 않는다.
상세 수치는 [summary.csv](summary.csv), [summary.json](summary.json)에 있다.

## 과거 자체 뷰어 기록 — 발표 기본 자료에서 제외

그림은 실행 중 SSH stdout/stderr와 `kubectl logs`를 읽은 **실시간 명령 출력 브라우저 화면**이다.
사후에 가상 로그를 만든 그림이나 데스크톱 터미널/Grafana 캡처가 아니다. 캡처별 JSON에 화면에
표시한 실제 레코드·관측 UTC·브라우저 버전을 보존했다. 19개 PNG와 첫 회차 연속 WebM 1개(97.32초)가 있다.

**1 MiB 요청과 같은 request ID의 응답, 계산·해제 완료:**

[과거 1회차 뷰어: 요청 대응·계산 결과](captures/evidence-s2-0928-01-PROBE_COMPLETE.png)

**3회차 검증·정상 회수 완료:**

[과거 3회차 뷰어: 검증·정상 회수](captures/evidence-s2-0928-03-RELEASED.png)

- [1회차 연속 실행 영상](captures/stage2-first-run-live.webm)
- [1 MiB 할당 직후 화면](captures/evidence-s2-0928-01-cudaMalloc_1MiB.png) · [그 화면 원본 JSON](captures/evidence-s2-0928-01-cudaMalloc_1MiB.json)
- [H2D 완료](captures/evidence-s2-0928-01-cudaMemcpy_H2D_1MiB.png) · [커널 동기화 완료](captures/evidence-s2-0928-01-cudaDeviceSynchronize.png)
- [전체 정수 검산](captures/evidence-s2-0928-01-ACCURACY.png)
- [2회차 실제 실행 완료](captures/evidence-s2-0928-02-PROBE_COMPLETE.png) · [최종 완료 화면](captures/evidence-s2-0928-03-COMPLETE.png)

발표에는 동일 request ID의 Guest/Worker 원본 로그와 불일치 0개·free 성공 출력을 사용한다.
구현 파트의 주장은 다음 범위다.

> “Guest의 CUDA 요청을 공유 메모리로 Worker에 전달하고, 같은 식별자의 응답을 회수했다.
> 1 MiB 정수 데이터의 복사·GPU 커널 실행·결과 회수·해제를 독립 실행 3회에서 확인했다.”

## 조건과 구현 변경

| 항목 | 실제 조건 |
|---|---|
| 서버·GPU | gpu-4, 물리 GPU 4개 중 GPU 1 한 개; `GPU-7d708c42-8d4a-16d5-0746-474567157aa3` |
| VM | 매회 새 VM 1개, Ubuntu 22.04.5, 8 vCPU·16 GiB RAM; 1단계와 같은 Guest 이미지 |
| GPU 자원 설정 | memory 4096 MiB, compute 50, Worker 1개·session 1개 |
| 공유 영역 / CPU | 64 MiB, Guest CPU 0–7 / Worker CPU 16–19; NUMA 메모리 강제 고정 없음 |
| 프로그램 | 직접 작성한 C/PTX [stage2_probe.c](../../stage2_probe.c); PyTorch 미사용 |
| 작업 | 단일 1 MiB allocation, H2D 1 MiB → uint32 add 19 → synchronize → D2H 1 MiB → 전수 비교 → free |
| 입력·커널 | seed 2027/2028/2029, input[i]=seed+i, reference[i]=input[i]+19, 1024 blocks × 256 threads, 커널 1회 |
| 준비 실행·측정 시간 | 별도 warmup 없음. 네 단계 사이 4초 대기는 화면 확보용이며 실행시간 지표로 쓰지 않음 |
| 반복 | 독립 allocation/generation/session/VMI/Worker 각 3개, 동일 probe·Guest library·Worker image |
| 추적 | Guest와 해당 실험용 Worker 이미지에만 `FLYT_TRACE_REQUESTS=1` |
| Driver / CUDA | 실제 Worker Driver 580.173.02, libcudart 12.8.90; CUDA 12.8.1 devel 이미지로 빌드 |
| HAMi-core | 실제 `libvgpu.so` SHA-256 `e98badc7ab64065af728fcca833ed372f16702d1e1c18eec01b1d8f6cbf7a9fb` |

기존 smoke/campaign에서 사용한 PTX 정수 `add.u32 +19` 연산과 ABI 등록·실행 경로를 재사용했다.
이번 probe는 발표의 1 MiB 예시를 전체 원소 검사로 연결하도록 한 allocation에서 연산한다.
기존 4096-byte smoke나 2 MiB campaign과 바이너리·입력이 같은 성능 비교 실험은 아니다.
중단했던 고정 작업량 **완료시간 캠페인은 재개하지 않았다**.

소스 기본 추적은 OFF다. Guest I/O thread와 Worker 큐 경계에 선택형 JSON 로그를 추가했고
공유 메모리 ABI·CUDA payload·스케줄링 정책은 변경하지 않았다. submit/respond 로그는 큐 성공 후
출력하며 Worker take는 dispatch 진입 전의 수신 관측이다. dispatch 완료 결과는 respond에 있다.
성능 오버헤드는 이번에 계측하지 않았다.

기준 커밋은 `02b24da4226abae05f553112f539e63d403d2b25`이고 여기에 기록된 추적 변경을 적용해 빌드했다.
[소스 스냅샷·해시](build/source-manifest.json), [실제 Containerfile](build/Stage2.Containerfile),
[Worker digest](build/worker-image.json), 각 회차 `command.json`의 Guest library/probe 해시로 특정한다.
Worker image는 `localhost/flyt-worker@sha256:bdac2a998228f13380efb7c80b38c7218ed639b12c00f9cc8d150d83f0c78dae`다.
기존 로컬 control_plane.py 수정은 이번 소스 커밋·Worker 빌드 변경에서 제외했으며 제어기 배포도 변경하지 않았다.

## 원본과 판정 근거

| 회차 | Guest stdout | Guest trace | Worker trace | 요청 대응 CSV | 전수검사 출력 | 최종 검증 |
|---|---|---|---|---|---|---|
| 1 | [stdout](runs/evidence-s2-0928-01/stdout.jsonl) | [Guest](runs/evidence-s2-0928-01/guest-stderr.txt) | [Worker](runs/evidence-s2-0928-01/worker-stderr.txt) | [CSV](runs/evidence-s2-0928-01/requests.csv) | [output.bin.gz](runs/evidence-s2-0928-01/output.bin.gz) | [PASS](runs/evidence-s2-0928-01/validation.json) |
| 2 | [stdout](runs/evidence-s2-0928-02/stdout.jsonl) | [Guest](runs/evidence-s2-0928-02/guest-stderr.txt) | [Worker](runs/evidence-s2-0928-02/worker-stderr.txt) | [CSV](runs/evidence-s2-0928-02/requests.csv) | [output.bin.gz](runs/evidence-s2-0928-02/output.bin.gz) | [PASS](runs/evidence-s2-0928-02/validation.json) |
| 3 | [stdout](runs/evidence-s2-0928-03/stdout.jsonl) | [Guest](runs/evidence-s2-0928-03/guest-stderr.txt) | [Worker](runs/evidence-s2-0928-03/worker-stderr.txt) | [CSV](runs/evidence-s2-0928-03/requests.csv) | [output.bin.gz](runs/evidence-s2-0928-03/output.bin.gz) | [PASS](runs/evidence-s2-0928-03/validation.json) |

각 디렉터리에는 `trace-binding.json`, `applied.json`, `identity.json`, `array-hashes.json`,
`runtime-libraries.json`, `gpu-processes.csv`, `released-channel.json`, `cleanup.json`도 있다.
GPU 프로세스 CSV의 host PID와 runtime-libraries의 host PID를 대조할 수 있다.
endpoint 로그의 PID는 각 PID namespace 값이므로 host PID와 같다고 가정하지 않는다.

- **정확성:** uint32 완전 일치, 허용 불일치 0. 압축한 실제 output을 공개하고 입력·기준은 seed로 재생성한다.
  SHA-256 비교와 전수 byte 비교도 통과했다. 부동소수점 오차나 임의 CUDA 함수 전체의 검증은 아니다.
- **요청:** 네 endpoint에서 allocation/generation/session/request ID, API·입력 크기와 응답 결과를 대조한다.
  모든 response의 transport_status=0이며 Runtime(도메인 1)/Driver(도메인 2) API 결과도 0이다.
- **malloc 의미:** 할당 요청값은 1,048,576 bytes지만 요청 payload는 크기를 담는 8 bytes다.
  응답 payload 8 bytes는 opaque allocation handle이고 Guest/Worker CPU 포인터가 아니다.
  같은 handle이 H2D·D2H·free에서 사용됐음을 확인했다. 요청 전 로그의 handle 0은 아직 응답이 없다는 뜻이다.
- **비동기 의미:** cuLaunchKernel 응답만으로 GPU 완료를 선언하지 않는다. 뒤의 cudaDeviceSynchronize와
  D2H 전수 결과 검사를 함께 사용한다. 두 endpoint의 단조 시각은 빼서 지연으로 계산하지 않는다.
- **GPU 메모리:** 이 1 MiB는 애플리케이션 요청량이다. 전체 GPU 메모리와 같지 않으며
  4 GiB 한도·compute 50의 실제 제한 효과를 이번 결과로 주장하지 않는다.

## 회수·검증 및 남은 단계

각 회차 Released와 VMI/Worker 소실을 확인했다. [최종 감사](final-audit.json)는 기존 basic-vm UID
유지와 실험 GPU 프로세스 부재를 기록한다. [읽기 전용 backing 감사](backing-audit.json)에서
공유 PVC의 allocation 디렉터리도 비었음을 확인하고 임시 감사 Pod를 삭제했다.

[증거 검사 14개](build/evidence-tests.log)가 통과했다(기존 1단계 5개 + 2단계 9개).
새 추적의 명시적 opt-in, 다른 세션·할당·응답 누락·중복·CUDA 오류·응답 크기 불일치 거절을 포함한다.
C 회귀 검사 5개와 root layout 검사 6개도 통과했다. 빌드 컨테이너 의존성 때문에 초기 통합 실행이
중단된 과정은 [재현 문서](REPRODUCE.md)에 구분했으며 실제 GPU 3회 실행에는 실패가 없었다.

I2의 요청 왕복·정수 정확성·실제 화면은 확보됐다. VM별 메모리 한도(I3), 연산 제한 진단(I4),
직접 실행·이전 FLYT TCP 대비 오버헤드(P1/P2)는 이 결과의 완료 범위에 포함되지 않는다.
공개 파일의 [SHA256SUMS](SHA256SUMS)와 [오프라인 재검증·재현 절차](REPRODUCE.md)를 함께 제공한다.
