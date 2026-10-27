# 1단계: cudaMemset의 과도한 동기화 제거 계획

후속 실제 VM 실험(2026-10-27): PCI BAR 통합·자식 장애 복구·VM 세대 전환 검증과
Flyt/control/candidate 각 5개 VM 성능 비교를 완료했다. control 대비 실행시간 34.3% 감소,
Flyt 대비 종합 10.0% 증가로 승격 조건 미충족. 운영·main·릴리스 이미지·Helm 변경 없음.
[결과와 검증 한계](../results/20261027-path-optimization-vm/REPORT.md),
[다음 개선안](../results/20261027-path-optimization-vm/NEXT-STEPS.md). 아래 준비/검증 전 표기는 과거 기록이다.

작성일: 2026-10-27 KST. 상태: 설계 완료, 제품 코드 구현·빌드·GPU 실행·배포 전.

후속 검증(2026-10-27): 별도 경로 최적화 후보에서 구현·빌드·mock·호스트 SHM 및 실제 GPU
정확성 검사를 완료했다. 응답 상태 초기화와 native memset 오류 유지 처리를 보완했다.
[검증 결과](../results/20261027-path-optimization-validation/README.md). 아래 내용은 최초 계획이며,
실제 VM 통합·성능 비교·운영 반영은 별도 단계다.

## 목적과 범위

VMWeave의 `cudaMemset()`을 native CUDA 의미에 맞게 전달하여 요청당 추가 왕복과 불필요한 device-wide synchronization을 제거한다. 이번 단계는 계획 문서만 작성한다. 후속 구현은 별도 작업 공간에서 준비하고, 진행 중 캠페인의 실행 환경은 변경하지 않는다.

대상은 현재 지원하는 device allocation의 1차원 `cudaMemset`이다. `cudaMemsetAsync`, 복사/bulk 경로, Broker 구현, Worker 프로세스 분리, 대기 설정, MPS/HAMi, Graph 및 managed/pinned-host memory 지원 확장은 범위 밖이다. Flyt 대비 성능 역전은 성공 조건이 아니다.

## 확인한 현재 동작과 목표

- `runtime/shm/src/guest_torch.c`: `cudaMemsetAsync(..., 0)` 성공 후 `cudaDeviceSynchronize()` 호출. 정상 경로는 두 번의 exchange다.
- `runtime/shm/src/torch.c`: 기존 `VMWEAVE_MEMSET`은 40-byte descriptor를 검증하고 native `cudaMemsetAsync`를 호출한다.
- `runtime/shm/include/vmweave_torch.h`: 기존 opcode는 enum 자동 증가를 포함하므로 중간 삽입 시 ABI 번호 변경 위험이 있다.
- `runtime/shm/src/worker_sessions.c`: 해당 opcode 범위는 torch dispatcher로 전달된다.
- `runtime/shm/src/guest.c`: transport unsupported가 801로 변환된다. 최종 반환 코드만으로 transport 거절과 native CUDA 오류를 항상 구별할 수 있다고 가정하지 않는다.

목표 경로:

```text
현재: Guest cudaMemset → remote memsetAsync → remote deviceSynchronize → 반환
후보: Guest cudaMemset → 전용 opcode → backend native cudaMemset → 반환
```

호출 반환은 GPU 완료와 같지 않다. CUDA 12.8 문서상 pinned host memory를 제외한 memset은 host 관점에서 비동기이며, synchronous 형태는 default stream을 사용한다. 이번 대상은 device allocation이다. native 호출도 내부 사유로 block할 수 있으므로 “항상 즉시 반환”을 보장하지 않는다.

근거: [CUDA 12.8 API synchronization behavior](https://docs.nvidia.com/cuda/archive/12.8.0/cuda-runtime-api/api-sync-behavior.html), 확인 2026-10-27.

## 설계 결정

### 명시적 opt-in과 별도 opcode

- 후보 설정 이름은 `VMWEAVE_NATIVE_MEMSET=1`, 기본은 기존 경로 유지. 환경 옵션은 프로세스 초기화 시 한 번 결정하고 VMWeave의 기존 환경변수 처리 방식을 따른다.
- `VMWEAVE_MEMSET_NATIVE`를 별도 명시적 번호로 추가한다. 구현 전 전체 opcode 사용을 검색하여 미사용 번호를 확정한다. 기존 enum 번호와 wire semantics는 변경하지 않는다.
- 기존 40-byte descriptor 형태를 재사용한다: handle, offset, bytes, stream, value, reserved. 새 opcode에서는 stream=0, reserved=0만 허용한다.
- backend는 길이·범위·handle·세션 소유권을 검사한 후 native `cudaMemset(address, value, bytes)`를 한 번 호출한다. GPU 완료를 강제하는 후속 sync를 추가하지 않는다.
- Guest는 하나의 lock 구간에서 ref 검증·descriptor 작성·exchange를 수행한다. 공개 `cudaMemsetAsync`를 호출하는 식으로 mutex를 중첩하지 않는다.
- 새 응답은 output payload가 없어야 한다. 오류는 성공으로 바꾸지 않고 기존 세션 fencing/오류 전달 계약을 유지한다. last-error 처리와 alias/export 동작도 기존 public wrapper와 대조한다.

### 첫 후보의 버전 호환 정책

가장 작은 구현을 위해 첫 후보는 opt-in + 일치하는 Guest/Worker 조합으로 한정한다. 별도 capability 프로토콜을 동시에 추가하지 않는다.

| 조합 | 기대 동작 |
|---|---|
| 새 Guest OFF + 기존/새 Worker | 기존 두 요청 경로 |
| 기존 Guest + 새 Worker | 기존 opcode 동작 보존 |
| 새 Guest ON + 새 Worker | 새 opcode, native memset 한 번 |
| 새 Guest ON + 기존 Worker | 명시적 unsupported, GPU memset 부작용 없음 |

최종 오류 801만 보고 이전 경로로 자동 재전송하지 않는다. timeout/연결 단절 뒤에도 재전송하지 않는다. 공개 기본 활성화 및 자동 호환 협상은 후속 범위다. 나중에 fallback이 필요하면 부작용 없는 capability 조회로 실행 전에 결정한다.

## 진행 중 실험과의 분리

1. 구현 시작 시 기준 commit, 관련 파일 SHA256, 필요한 미커밋 변경을 기록한다. 현재 작업 공간에는 bulk 관련 수정과 다수의 실험 산출물이 있으므로 HEAD만 복제하면 같은 baseline이라고 가정하지 않는다.
2. 별도 worktree/격리 복제본과 전용 build·artifact 경로를 사용한다. 필요한 미커밋 기반 변경은 명시적 patch와 해시로 가져오며 기존 작업을 commit/stash/reset하지 않는다.
3. 기존 Guest 라이브러리, Broker, Worker, 이미지 태그, 공유 경로 및 캠페인 runner를 수정하지 않는다. 현재 실험은 다음 반복에서 새 프로세스를 만들 수 있으므로 새로 읽는 파일까지 보호한다.
4. 실행 중 실험의 호스트·CPU/GPU 자원은 아직 실시간 감사하지 않았다. 같은 호스트에서 build/test를 실행하지 않고 별도 자원이 확인되면 사용한다. 격리 자원이 없으면 코드·테스트 작성까지만 준비한다.
5. GPU 검증은 기존 캠페인 종료·자원 회수 확인 후 별도 캠페인으로 한다. 새 이미지/바이너리 digest를 쓰고 기존 경로를 덮어쓰지 않는다. 자동 배포·운영 교체는 이 계획에 포함하지 않는다.

## 구현 산출물과 순서

1. 기준 소스 manifest 및 별도 작업 공간 확보.
2. 헤더의 새 opcode와 Worker native handler 추가.
3. Guest opt-in wrapper 추가. OFF 경로는 기존 동작 유지.
4. GPU 없이 실행 가능한 실제 C wrapper/dispatcher 테스트 및 CUDA 검증 probe 작성.
5. `API_SUPPORT.md`에 지원 범위·반환 의미·호환성·rollback 설정 문서화.
6. 격리 자원에서 빌드·mock 검증 후, GPU 시험 준비 상태를 보고한다. GPU 검증 전에는 구현 완료와 성능 검증 완료를 구분한다.

예상 제품 변경 파일: `include/vmweave_torch.h`, `src/guest_torch.c`, `src/torch.c`, `API_SUPPORT.md`. Broker/queue/worker lifecycle 변경이 필요해지면 첫 단계 범위를 재검토한다.

## 검증 계획

### GPU 없는 검증

문자열 검색으로 구현을 확인하는 테스트 대신 실제 wrapper와 dispatcher를 mock transport/CUDA backend에 연결한다.

- ON: 정상 호출마다 memset opcode 한 번, 추가 device sync 0회. OFF: 기존 호출 순서 유지.
- Worker가 native `cudaMemset`을 호출하며 기존 async opcode는 여전히 `cudaMemsetAsync`를 사용하는지 확인.
- descriptor 크기 오류, reserved/stream 비정상, invalid/stale handle, 범위 초과에 native CUDA 호출이 발생하지 않는지 확인.
- native 오류 반환, 잘못된 응답 길이, 연결 실패·timeout에 성공 반환 또는 재전송이 없는지 확인.
- 구 Guest/Worker 호환 표의 각 조합 확인. 0-byte 및 signed value 인코딩은 기존 ref validation 계약과 native 의미를 구분해 확인한다.
- 기존 session/transport 및 naming 검사를 변경 파일과 관련된 범위로 실행한다. 정확한 명령은 테스트 구현 후 재현 문서에 고정한다.

### GPU 정확성·의미 검증 — 캠페인 종료 후

동일 CUDA 12.8 native 실행을 의미 대조군으로 사용하고 default-stream 컴파일 모드를 기록한다. 첫 단계는 기존 지원 모드로 한정하며 PTDS 신규 지원을 주장하지 않는다.

- 0, 1, 255, 256 및 큰 크기, 내부 offset, 끝 경계, 여러 value(0/0x5a/0xff/-1)를 확인한다. 유효 범위 밖 canary가 유지되는지 검사한다. 유효 device pointer의 0-byte 호출과 NULL/invalid pointer는 별도 조건이다.
- memset → default-stream 검증 커널 → 명시적 완료 → D2H로 정확성을 검사한다. 반환 직후 결과를 동기화 없이 읽지 않는다.
- nonblocking stream의 유한 시간 작업과 default-stream memset을 함께 실행하고 event/query 기록으로 불필요한 전체 장치 대기가 제거되는지 조사한다. native도 내부적으로 block할 수 있으므로 한 번의 시간 임계값을 API 의미의 유일한 합격 조건으로 삼지 않는다.
- 기존 `cudaMemsetAsync`의 명시적 stream 순서, 호출 뒤 free, 새 세션 생성/종료가 회귀하지 않는지 확인한다.
- 즉시 오류는 호출에서, 지연 실행 오류는 후속 완료 지점에서 관측될 수 있음을 반영한다. 오류 700 등 실제 장애 주입은 이 작은 성능 시험에 넣지 않고 mock 검증과 분리한다.

### 성능 검증

같은 후보 바이너리의 OFF/ON을 비교한다. Flyt와의 전체 재비교는 이번 단계의 필수 조건이 아니다.

- 조건별 독립 세션 최소 5회, 순서는 사전 고정 seed로 균형 배치. warmup과 초기화·할당은 별도 기록하고 제외한다.
- 크기 제안: 4B, 4KiB, 1MiB, 16MiB. 모든 조건의 GPU·CPU 배치·quota·bulk/cache 옵션을 고정한다.
- A: API 반환 latency. B: memset + 명시적 완료 latency. C: N회 memset 후 마지막 sync를 포함한 batch 완료 시간. OFF의 wrapper 내부 sync도 그대로 비용에 포함한다.
- CPU monotonic 시간으로 측정하고 p50/p95/p99, 세션별 값, CPU 비용을 기록한다. 내부 반복을 독립 세션 표본으로 세지 않는다.
- opcode별 요청 수는 별도 진단에서 확인하고 상세 계측을 끈 실행을 공식 성능값으로 사용한다.
- 응용 시험은 실제 memset 호출 수를 먼저 조사해 해당 경로를 사용하는 작은 workload 하나를 선택한다. 호출이 없으면 그 workload의 개선을 주장하지 않는다.

## 완료 기준과 rollback

- 의미·정확성·호환성 검증을 통과하고 ON의 wrapper가 두 요청에서 한 요청으로 감소하며 추가 device sync를 발행하지 않는 것을 확인한다.
- API 반환 시간 감소만으로 GPU 완료 성능 향상을 선언하지 않는다. 완료 포함 지표와 함께 보고하고, 표본이 부족하거나 결과가 불확정이면 그대로 기록한다.
- 성능이 나쁘거나 불확정이면 opt-in 후보로 남긴다. 결과를 보고 임계값을 바꾸거나 유리한 반복만 선택하지 않는다.
- rollback은 새 프로세스에서 옵션을 OFF로 시작하는 것이다. 실행 중 세션의 환경/바이너리를 바꾸지 않는다. 후보 Worker는 기존 opcode를 유지하므로 OFF Guest를 지원한다.
- 산출물: 소스 diff·기준/후보 해시, 테스트 결과, protocol, 전체 원시 표본, 요청 수 진단, 분석, 자원 회수 기록. 기본 활성화·운영 적용은 별도 단계로 판단한다.
