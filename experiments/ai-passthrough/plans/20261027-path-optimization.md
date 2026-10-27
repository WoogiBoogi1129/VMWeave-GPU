# VMWeave 경로 최적화 전체 코드 수정 계획

후속 실제 VM 실험(2026-10-27): PCI BAR 통합·자식 장애 복구·VM 세대 전환 검증과
Flyt/control/candidate 각 5개 VM 성능 비교를 완료했다. control 대비 실행시간 34.3% 감소,
Flyt 대비 종합 10.0% 증가로 승격 조건 미충족. 운영·main·릴리스 이미지·Helm 변경 없음.
[결과와 검증 한계](../results/20261027-path-optimization-vm/REPORT.md),
[다음 개선안](../results/20261027-path-optimization-vm/NEXT-STEPS.md). 아래 준비/검증 전 표기는 과거 기록이다.

작성일: 2026-10-27 KST. 상태: 설계 문서, 아래 P1~P7 제품 코드 미구현.

후속 상태(2026-10-27): 별도 후보에서 P0~P7a 구현과 빌드·회귀·CPU sanitizer·호스트 SHM/GPU
정확성 검사를 수행했다. [검증 결과](../results/20261027-path-optimization-validation/README.md).
아래 실행 제한과 미구현 표기는 최초 계획 시점의 기록이며, 실제 VM 통합·성능 비교·운영 반영은 남아 있다.

## 1. 목적·실행 범위

bulk ON 이후에도 남는 중간 복사, 할당, 프로세스/스레드 전달 및 대기를 줄인다. 성능 개선 가능성을 코드 후보로 준비하고, 현재 캠페인 종료·회수 확인 후 실제 빌드와 검증 실험으로 판단한다. 이 문서 작성은 제품 코드 적용이나 성능 검증 완료를 의미하지 않는다.

선행 [native memset 계획](20261027-memset-native.md)의 후보는 별도 경로 `/home/ubuntu/taeuk/vmweave-memset-native-20261027`에 준비돼 있다. 해당 후보도 아직 C 빌드/mock/GPU 검증을 통과하지 않았다. 검증된 기반 버전으로 취급하지 않는다.

기존 실험 호스트에서는 compile/link, unit test 실행, 이미지 빌드, GPU 실행을 수행하지 않는다. 코드·테스트 작성과 제한적인 텍스트/구문/patch 검토만 진행한다. 별도 빌드 자원이 확인되기 전에는 “빌드 가능”, “회귀 없음”, “검증 완료”를 주장하지 않는다. 이후 빌드 실패 가능성을 사전 검토로 낮출 수 있지만 없앨 수는 없다.

## 2. 현재 비용과 목표

현재 주요 H2D 경로:

```text
응용 → Guest 요청 버퍼 → Guest/Broker arena
     → Broker private 요청 버퍼 → VM/host SHM
     → Worker private snapshot → host Unix socket → CUDA 자식 버퍼 → CUDA
```

Broker는 `ctypes` 호출 뒤 C I/O 스레드로 요청을 넘기며, Worker 부모는 별도 CUDA 자식에게 요청/응답을 전달한다. bulk 최적화는 Guest/Broker 소켓의 큰 payload만 우회한다. D2H 및 작은 요청 경로는 별도로 분석한다.

이번 설계는 응용에 BAR 접근권을 주지 않고, 세션별 CUDA 프로세스·검증 경계·오류 전달을 유지하는 방향이다. 최초 목표는 단일 outstanding request를 유지하면서 불필요한 이동을 줄이는 것이다. zero-copy GPU 실행이나 Flyt 대비 우위를 미리 주장하지 않는다.

## 3. 변경 단위와 순서

| 단계 | 코드 변경 | 줄이려는 비용 | 의존 관계 |
|---|---|---|---|
| P0 | native memset 전용 요청 | 추가 왕복·device sync | 선행 별도 후보 |
| P1 | Guest 원본에서 bulk arena로 직접 복사 | H2D 요청 버퍼 경유 | 기존 bulk ON |
| P2a | Broker 버퍼 재사용 | 매 요청 할당·초기화 | 독립 |
| P2b | Worker caller-owned snapshot API | 매 요청 malloc/free | 독립 |
| P3 | 분리 입력 submit/exchange, Broker staging 제거 | arena→private→SHM 중 한 단계 | P1, P2 계약 |
| P4 | Worker 부모/자식 세션 전용 payload arena | host 소켓 payload 이동 | P2b |
| P5 | Broker 요청 처리와 transport owner 통합 | 내부 스레드 전달·일부 Python 처리 | P3의 분리 입력 계약 |
| P6 | 제한적 spin·알림 방식 | polling 지연·깨움 비용 | 구조 변경과 별도 대조 |
| P7 | pinned/event pool, 이후 pipeline | 비동기 할당·직렬 처리 | 별도 후속 설계 |

첫 코드 준비 묶음은 P1·P2a·P2b다. P3/P4는 별도 patch로 준비한다. P5 이후는 아래 설계 경계를 먼저 명확히 하고 구현한다. 빌드할 수 없는 동안 하나의 대형 통합 patch로 합치지 않는다. P0의 기본 OFF 경로를 기준으로 P1/P2를 검토하고, P0 ON과의 결합은 별도 검증한다.

## 4. 공통 불변 조건

- 기존 opcode 번호, wire layout, exported ABI를 유지한다. 새 기능은 additive interface 또는 버전이 명시된 새 protocol로 도입한다.
- metadata는 private snapshot으로 검증한다. opcode/handle/길이/offset/epoch를 검증 후 공유 메모리에서 다시 읽지 않는다.
- shared payload는 원자적 snapshot을 보장하지 않는다. 동시 데이터 변경이 있어도 routing·bounds 검증을 우회하지 못해야 한다. 공개 응용의 정상 사용에서는 완료 전 버퍼를 수정하지 않는다.
- 응용 fork 후 사용 거절, 세션 epoch 검사, 실패 상태 고정, health 검사 및 cache invalidation을 모든 새 경로에서 유지한다.
- fallback은 전송 전 협상 또는 확실한 미실행 판단에서만 가능하다. 실행 여부가 불명확한 timeout/EOF/오류 뒤 재전송하지 않는다.
- 검증 실패·길이 초과·정수 overflow는 publish/실행 전에 거절한다. 합계 길이는 덧셈 후가 아니라 남은 용량과 비교한다.
- 요청 버퍼는 소비 완료, 응답 버퍼는 수신 완료, 비동기 CUDA staging은 CUDA 완료를 기준으로 재사용한다. 세 시점을 혼동하지 않는다.
- 세션 종료·실패 때 메모리/FD/자식 프로세스 소유권을 회수한다. 이전 mapping을 가진 프로세스가 있어도 새 세션이 그 메모리를 재사용하지 않는다.
- 기존 로그·실험 결과·빌드 경로·이미지 태그·운영 파일을 덮어쓰지 않는다.

## 5. P1 — Guest 원본 → bulk arena 직접 복사

대상: `runtime/shm/src/guest.c`, `src/broker_client.c`, `include/vmweave_guest.h` 또는 새 내부 broker 헤더.

현재 `vmweave_guest_copy()`가 H2D payload를 연속 요청에 담은 후 `bulk_request()`가 arena로 복사한다. 새 내부 인터페이스는 검증된 descriptor와 원본 payload pointer/length를 별도로 받는다.

구현 방식:

1. 기존 copy 전체 범위 검증, chunk 제한, zero-length 처리, 공개 Guest lock을 유지한다.
2. Broker 내부의 PID 검사→lock→연결/협상→health→전송→오류/cache 처리를 공통 helper로 추출한다. 기존 `vmweave_broker_exchange`와 새 copy 경로가 같은 helper를 사용한다. lock을 잡은 helper가 공개 exchange를 재호출하지 않는다.
3. bulk가 확실히 사용 가능한 synchronous H2D일 때 원본에서 arena로 한 번 복사하고 기존 48-byte descriptor를 보낸다. D2H는 현재 arena→사용자 복사를 유지한다.
4. 미지원/임계값 미만/async/D2D/direct-SHM 경로는 실행 전에 기존 요청 생성 방식으로 선택한다. API 이름만 보고 native pointer를 wire에 보내지 않는다.
5. 1MiB threshold, 16MiB chunk 및 실제 협상 상한은 유지한다. 성능 비교 중 임계값을 동시에 바꾸지 않는다.

초기 opt-in은 기존 `VMWEAVE_BULK_COPY`와 구분 가능한 후보 옵션으로 관리한다. 최종 옵션명은 하나의 설정 표에서 확정하고 신규 FLYT alias는 추가하지 않는다. 같은 binary의 기존 bulk 경로가 대조군으로 남아야 한다.

검증 준비: 실제 C client + mock Broker로 byte-for-byte payload, 경계 전후, chunk 순서, old Broker, fallback 전 미전송, 부분 송수신, timeout/EOF, fork, health/cache invalidation 확인. 직접 arena 경로에서 Guest 임시 payload 복사가 사라지는지 계수한다.

## 6. P2a — Broker 버퍼 재사용

대상: `runtime/shm/control/guest_broker.py` 및 관련 mock Broker 테스트.

- 세션별 request/output scratch를 high-water 방식으로 확보하고 상한을 둔다. 매 요청 큰 `ctypes.create_string_buffer()`를 호출하지 않는다.
- 초기화/확장 시 완성된 새 버퍼를 설치한다. allocation 실패 시 기존 버퍼·세션 상태를 보존하거나 명시적으로 실패 처리한다.
- 늘어난 capacity와 전송할 logical length를 분리한다. 재사용 버퍼에서 `ctypes.sizeof(buffer)`를 요청 길이로 전달하지 않는다.
- 일반 응답은 유효한 `got` bytes만 복사/전송한다. 큰 버퍼의 `.raw` 전체를 먼저 bytes로 만들지 않는 방식으로 바꾼다.
- `mmap.from_buffer` 객체 및 memoryview가 남은 상태에서 mmap을 close/resize하지 않는다. ctypes 객체와 pointer는 C I/O 완료까지 살아 있어야 한다.
- 세션 종료에 scratch를 회수한다. 실패 후 이전 output을 정상 응답으로 내보내지 않는다.

이번 단계는 할당 최적화다. private payload 복사 제거(P3)를 함께 하지 않는다. 테스트는 크기 증가/감소 반복, 짧은 응답 뒤 잔여 byte 노출, allocation 실패, EOF 및 cleanup의 exported-buffer 참조 문제를 포함한다.

## 7. P2b — Worker snapshot 메모리 소유권 분리

대상: `shm-queue/include/vmweave_shm_queue.h`, `shm-queue/src/queue.c`, `src/worker_sessions.c`. 필요하면 `src/worker.c`는 기존 allocating API를 계속 사용한다.

현재 `vmweave_shm_request_release(q)`는 `q->input`을 무조건 free한다. 단순히 pool pointer를 기존 request에 넣으면 invalid free/use-after-free 위험이 생긴다.

권장 설계는 별도 `worker_take_into(channel, request, storage, capacity)` API다.

- 기존 `worker_take`/`request_release` 의미를 유지한다. 새 API의 caller-owned storage는 호출자가 관리하며 기존 release에 넘기지 않는다. 별도 clear/release-borrowed 계약을 헤더에 명시한다.
- ABI request struct에 ownership flag를 임의로 추가하지 않는다. 내부 공통 검증 helper를 통해 allocating/into 구현의 검증 조건을 일치시킨다.
- 처음에는 협상 가능한 최대 요청 크기의 bounded buffer를 세션/slot에 한 번 확보하는 방법을 우선한다. 상한과 전체 메모리 증가를 기록한다.
- 작은 capacity면 ring consume, next id 변경, CUDA 실행 없이 거절한다. 필요한 길이를 제공한다면 오류 응답과 구별하는 local-only 결과로 정의한다.
- snapshot은 기존 volatile bounded load 의미를 유지한다. 고성능 memcpy로 바꾸는 작업은 별도 검토 대상으로 남긴다.
- 부모는 자식 응답까지 이 버퍼를 소유한다. 새 요청/세션의 재사용은 이전 사용 종료 후에만 허용한다.

테스트: 실제 queue 구현의 경계/identity/순서/too-small buffer 미소비, 반복 take/respond, allocating API와 into API의 독립 수명, 종료 중 포인터 사용, 메모리 검사 도구. mock 성공뿐 아니라 이후 ASan/UBSan 실행도 계획한다.

## 8. P3 — Broker payload staging 제거

대상: `src/guest.c`, `include/vmweave_guest.h`, queue 헤더/구현, `control/guest_broker.py`.

새 local API는 소수의 segment(header와 payload)로 입력을 받는다. 가칭 `submit_parts`와 `guest_exchange_parts`이며 명칭은 구현 시 고정한다. VM/host wire 형식은 기존 연속 payload로 유지한다.

- header/session envelope는 Broker private 값으로 구성한다. arena에서는 데이터 bytes만 읽는다.
- 모든 segment 길이·pointer·합계 용량·identity를 검증한 뒤 기존 SHM payload 영역에 순서대로 복사한다. 부분적으로 썼더라도 publish 전 실패는 실행되지 않아야 한다.
- 마지막 copy 완료 뒤 기존 release publication을 수행한다. 게시 전 임의 완료 flag를 세우지 않는다.
- 현재 I/O 스레드에 전달할 segment 목록은 private 사본으로 보관한다. Python arena와 header의 수명은 응답/실패 정리까지 유지한다.
- 기존 연속 submit API를 유지하고 새 helper를 내부 공유한다. queued receive의 “출력 버퍼가 작으면 receive만 재시도” 계약을 깨지 않는다.
- Python이 새 C symbol을 찾지 못하면 전송 전에 기존 staging 경로를 선택한다. 신호/timeout/실행 중 오류 뒤 경로 전환은 하지 않는다.

목표: `arena → Broker private payload → SHM`을 `arena → SHM`으로 줄인다. Worker snapshot은 보존한다. metadata가 있는 공유 영역을 native CUDA에서 그대로 해석하도록 바꾸지 않는다.

테스트: segment empty/overflow/경계, publish 전 오류, 이전 라이브러리 조합, I/O 완료 전 mapping 수명, 공유 payload 변경에도 routing 불변, 모든 직접·Broker 경로.

## 9. P4 — host 부모/자식 전용 payload arena

대상: `src/worker_sessions.c`, 새 내부 `session_ipc.[ch]`, CMake 타깃 의존성. Guest/VM wire는 유지한다.

부모와 CUDA 자식 사이의 socket은 작은 제어/응답용으로 유지하고, 큰 synchronous H2D/D2H payload를 세션 전용 memfd arena로 이동한다. 작은 요청과 async는 첫 후보에서 기존 소켓 경로를 사용한다.

- 부모가 새 세션마다 memfd를 생성하고 크기 변경을 seal한다. FD 전달 또는 exec 상속 중 한 방식만 구현하고 CLOEXEC/허용 FD 목록을 명시한다. 세션 종료 후 새 memfd를 사용한다.
- 제어 message에 version, sequence, direction, slot, offset, length를 명시적으로 인코딩한다. 기존 C struct raw layout에 필드를 추가해 구 peer가 오해하도록 만들지 않는다. 시작 시 부작용 없는 handshake로 모드를 결정한다.
- P2b의 snapshot 목적지를 host arena로 지정하는 방향을 검토한다. Guest가 쓸 수 없는 host-only 영역이며 부모가 payload를 복사하고 제어 descriptor는 private socket 메시지로 보낸다.
- CUDA 자식도 descriptor와 device handle/bounds를 검증한다. 부모는 자식 응답을 신뢰하지 않고 sequence·길이·capacity·status를 검증한다. 자식이 반환한 pointer를 부모가 역참조하지 않는다.
- D2H는 자식이 arena에 결과를 만들고 부모가 검증된 길이만 VM SHM으로 복사한다. host arena에서 VM SHM으로 가는 마지막 복사는 남는다.
- 초기 상태는 FREE → FILLING → SUBMITTED → COMPLETED → FREE. 실패는 FAILED 후 폐기하며 timeout 상태에서 FREE로 되돌리지 않는다.
- synchronous H2D의 native API 반환 후 staging 재사용 가능 조건을 CUDA 명세와 backend 구현에 맞춰 확인한다. async를 추가할 때는 event 완료를 별도 경계로 설계한다.
- 자식 crash 시 pid/starttime, FD 종료 및 reap을 기존 방식대로 처리한다. 기존 kill/reap/fencing을 polling 최적화와 함께 바꾸지 않는다.

테스트: 각 상태의 socket 단절·자식 exit, bad sequence/length/direction, 구/신 조합 handshake, D2H 오류 시 stale output 차단, FD 누수·잔존 mapping·새 세션 비공유. 실제 GPU 오류 주입은 별도 격리 캠페인에서만 한다.

## 10. P5 — Broker hot path와 transport owner 통합

대상: 새 native Broker/transport owner 모듈, `src/guest.c`의 transport 코드 분리, CMake, 서비스 실행 설정(별도 후보에서만).

Python 코드를 전부 교체하는 것보다 먼저 reusable transport owner context를 분리한다. 공개 Guest API는 기존 I/O-thread 어댑터를 유지하고, 후보 Broker는 같은 native thread에서 open→HELLO→submit/receive→heartbeat→close를 수행한다.

- 단순히 owner 검사를 제거하거나 다른 스레드에서 기존 channel을 사용하지 않는다.
- 이벤트 루프는 로컬 socket, SHM receive 확인, heartbeat, cache lease/status, disconnect를 처리한다. blocking recv 때문에 peer failure/timeout을 무기한 놓치지 않게 deadline을 유지한다.
- 기존 Broker의 epoch 생성, busy 거절, session close, fork/EOF 처리, memfd 협상, protocol 오류 정책을 동작별로 이식한다.
- Python Broker와 native Broker는 실행 시 선택하는 별도 타깃으로 둔다. 자동 교체하지 않는다. 요청/응답 differential test로 동일 계약을 확인한다.

구조 변경 폭이 크므로 P1~P4의 효과가 검증되기 전 기본 구현으로 승격하지 않는다. 코드만 준비해도 “Python 제거 효과”를 수치로 주장하지 않는다.

## 11. P6/P7 — 후속 최적화 경계

P6a는 기존 wait 옵션의 bounded spin/sleep 조합을 활용하는 실험 설정부터 준비한다. CPU affinity 단일 코어 강제나 무제한 spin은 기본값으로 적용하지 않는다. latency와 전체 CPU time/request를 함께 평가한다.

P6b host 내부 eventfd 알림은 wait-before-check/notify-before-wait race와 lost wakeup을 정의한 뒤 별도 구현한다. 응답 publication과 acquire 확인 순서를 유지한다. VM/host 사이에 일반 futex/eventfd를 그대로 공유할 수 있다고 가정하지 않는다. IVSHMEM interrupt 지원 및 domain/mapping 변경이 필요한 cross-VM 알림은 이번 코드 준비 묶음에서 제외한다.

P7a `src/async.c`의 per-request cudaHostAlloc/event 생성·해제를 bounded per-session pool로 바꾸는 후보를 준비할 수 있다. size class, 메모리 상한, event 완료 후 재사용, 오류 뒤 in-flight buffer 보존/프로세스 정리를 명시한다. pool exhaustion은 기존 backpressure 의미를 유지한다.

P7b 다중 outstanding request/pipeline과 D2H 조기 반환은 현재 단일 pending/arena 및 완료 계약을 바꾼다. 새 request-id/slot/credit·stream ordering·부분 실패·guest destination lifetime protocol 없이는 구현하지 않는다. 첫 전체 수정 묶음에는 포함하지 않고 P1~P7a 검증 결과에 따른 별도 설계로 남긴다.

## 12. 빌드 불가 기간의 코드 작성·검토 절차

각 단계는 다음 산출물을 갖춘 별도 patch와 후보 스냅샷으로 준비한다.

1. 기준 commit + 필요한 미커밋 bulk 변경 + 파일 해시를 고정한다. native memset 후보와 원본 runtime을 혼합할 때 포함 여부를 manifest에 명시한다.
2. 함수 signature, 선언/정의/호출자, exported symbol/alias, enum 숫자, CMake include/link 의존성 목록을 작성한다.
3. request/response별 소유자, allocation/free 담당, 정상/오류 반환 시 수명 표를 만든다.
4. lock 획득 순서를 정리한다. Guest lock→Broker lock 등 현재 순서를 유지하고 공개 API의 재진입으로 같은 lock을 다시 얻지 않도록 한다.
5. short I/O/EINTR/EOF/timeout/allocation 실패/unsupported 경로를 정상 경로와 함께 작성한다. in-flight 재시도는 금지한다.
6. 기능별 옵션은 초기화 시 한 번 읽고 기본 OFF로 둔다. 의존 기능이 없으면 전송 전 legacy 선택 또는 명시적 unsupported로 처리하며 선택된 경로를 기록한다. 세션 중간 전환은 금지한다.
7. 실제 소스에 연결하는 mock/경계 테스트를 작성한다. 구현을 흉내 낸 별도 함수나 문자열 검색을 기능 검증으로 쓰지 않는다.
8. Python AST·shell syntax·patch whitespace/적용 가능성·관련 원본 파일 해시를 저부하로 확인한다. C 전처리·구문·link·테스트는 미실행 상태로 남긴다.
9. 원본 product 파일·진행 중 campaign 경로와 후보를 다시 대조한다. 후보 파일을 기존 runner가 참조하지 않는지 확인한다.

정적 검토로 확인하지 못한 ABI/컴파일러/라이브러리/동시성 문제는 단계별 미확인 목록에 남긴다. 모든 단계의 설계를 끝냈다는 이유로 구현이나 검증 상태를 일괄 COMPLETE로 바꾸지 않는다.

## 13. 캠페인 종료 후 검증 순서

종료 process 확인과 시험 GPU/VM/backend/MPS 회수를 함께 확인한다. 상태 파일의 completed 값만으로 시작하지 않는다. 운영 작업이 없는 시험 예약과 CPU/NUMA 자원도 확보한다.

1. **빌드:** 원본과 단계별 후보를 동일 CUDA 12.8/컴파일러로 빌드. 공개 Guest/Worker 타깃, 직접 SHM 경로, legacy naming/link, exported symbols 확인.
2. **기능:** 작성한 실제 C mock 및 기존 관련 queue/broker/cache/session 테스트. CPU-only 코드에 ASan/UBSan 적용; sanitizer 실행을 성능값에 섞지 않음.
3. **경계·수명:** 0B/1B, 1MiB±1, 16MiB±1, multi-chunk, 반환 길이, 세션 종료·FD·mapping·allocation 누수 검사. fault injection은 mock부터 수행.
4. **GPU:** 전체 출력/canary, H2D/D2H/D2D, async stream 순서, 완료 전 버퍼 재사용 금지, memset ON/OFF 및 resource/session 회귀 확인.
5. **단계별 성능:** 같은 candidate binary의 기능 OFF/ON, 다른 옵션 고정. 각 조건 독립 세션 최소 5개, 균형 순서와 warmup을 사전 고정. 작은 호출 p50/p95/p99, 복사 GB/s, 완료 포함 시간, 전체 Guest/Broker/Worker CPU와 메모리 사용량 기록.
6. **결합 성능:** 개별 단계 검증 후 조합을 누적 비교한다. 결합 효과를 개별 효과 합으로 가정하지 않는다. 최소한 memset/bulk/부모자식 arena의 상호작용을 확인한다.
7. **응용 비교:** 동일 구성의 Flyt SHM·baseline VMWeave bulk ON·후보 VMWeave를 새로 측정한다. 과거 Flyt 수치를 새 후보의 정식 대조군으로 혼합하지 않는다.

공식 측정은 상세 trace 없이 수행한다. 복사 byte 수, 할당 횟수, syscall byte 수, API 전달 수, handoff 시간은 별도 진단으로 확인한다. Guest/host 시계를 직접 빼지 않는다. 호출 수 감소·CPU 사용 증가·실제 완료 시간 개선을 구분한다.

## 14. 완료·중단·되돌리기

각 단계의 상태를 DESIGNED / CODE_PREPARED / BUILD_PASS / FUNCTIONAL_PASS / GPU_PASS / PERFORMANCE_REVIEWED로 따로 기록한다. 실패·미실행을 성공으로 합치지 않는다.

정확성·세션 격리·오류 전파·호환성 회귀가 있으면 해당 후보는 다음 결합 단계에 넣지 않는다. 성능 차이가 불확정이면 원본 표본과 변동을 보고하고 기본값을 바꾸지 않는다. arbitrary threshold를 측정 후 정해 합격시키지 않는다.

rollback은 새 세션에서 해당 opt-in을 끄거나 기존 고정 artifact로 시작하는 방식이다. 진행 중 세션의 코드/공유 메모리 layout을 교체하지 않는다. 정책·운영 배포·main 병합은 검증 결과를 기반으로 별도 작업 범위를 확정한다.

단계별 보존 자료: 기준/후보 manifest, patch, 인터페이스·소유권 표, 테스트와 재현 명령, 미확인 항목, 전체 raw 결과, 분석, FD/메모리/자원 회수 감사. 빌드 전에는 후보 코드 패키지까지만 완료로 표시한다.
