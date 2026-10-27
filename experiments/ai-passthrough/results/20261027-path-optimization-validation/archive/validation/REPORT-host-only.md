# VMWeave 경로 최적화 코드 검증 결과

2026-10-27 KST. 별도 후보 소스의 빌드, 회귀 검사, CPU sanitizer, 실제 GPU를 이용한
호스트 SHM 경로 정확성 검사를 수행했다. 검증 중 제품 코드 두 곳을 수정했다.
실제 VM의 PCI BAR 연결과 Flyt 대비 성능 비교는 이번 결과에 포함되지 않는다.

## 검증 대상과 실행 환경

대상은 `source/runtime/shm`의 P0~P7a 후보다. P5는 Python Broker에서 직접 C owner를
호출하는 구현이며, P7b 다중 요청 파이프라인은 포함하지 않는다. 모든 신규 옵션은
기본 OFF 상태를 유지했다. 운영 라이브러리·이미지·VM·Kubernetes 리소스는 교체하지 않았다.
원본 저장소의 준비 당시 runtime 파일 91개는 해시가 동일하다.

- 빌드: 기존 이미지 `localhost/flyt-threeway-build:20261025-full`, GNU C 11.4.0,
  CUDA Toolkit 12.8.93, Release, 병렬 작업 수 2.
- GPU: GPU 0, `GPU-772181af-05a4-0c24-de59-8487bd37c142`만 CUDA에 노출했다.
  실제 HAMi 라이브러리와 테스트별 2 GiB 메모리 제한·개별 cache 파일을 사용했다.
  GPU 3의 기존 작업은 건드리지 않았다.
- 경로: 실제 Guest → 실제 Python Broker → SHM queue → 실제 session Worker 부모 →
  CUDA 자식. Broker의 PCI BAR mapping 함수만 테스트 전용 파일 mapping으로 대체했다.
  조건마다 새로운 channel, Broker, CUDA 세션을 만들고 종료했다.
- CPU/NUMA는 기본 스케줄링이다. HAMi utilization watcher에 오류 101 경고가 남았다.
  CUDA 데이터 검증과 Worker의 UUID/메모리 검사는 통과했지만 SM 제어와 성능의 근거로
  사용하지 않는다. 환경·ELF 해시·로드 라이브러리는 [environment.json](environment.json)에 있다.

시작 시 활성 Flyt fault campaign 프로세스와 해당 실험 Pod가 없고 GPU 0이 비어 있음을
확인했다. 이전 campaign의 저장된 상태는 11/50에 머물러 있어, 이 검증이 과거 캠페인
50회 전체 완료를 확인한 것은 아니다.

## 발견한 문제와 수정

1. `torch.c` dispatcher가 응답의 `transport_status`를 초기화하지 않았다.
   오류 응답 객체를 재사용하는 mock에서 다음 정상 요청까지 이전 오류가 남아 실패했다.
   요청 처리 시작 시 `VMWEAVE_SHM_OK`로 초기화했다. 실제 Worker는 매 요청 새 응답을
   만들지만 dispatcher 자체도 재사용에 안전하도록 보완했다.
2. P0의 `vmweave_guest_record_error(0)`가 이전 last-error를 지웠다.
   실제 libcudart는 오류 → 성공한 memset → peek/get 순서에서 이전 오류를 유지했다.
   새 helper는 실패 시에만 TLS 오류를 기록하고 호출 자체의 반환값은 그대로 돌려준다.
   실제 Guest ELF의 오류 유지·get/peek reset·스레드별 분리를 검사했고, GPU에서도
   오류 → 성공 → peek/get 순서를 다시 확인했다. 다른 기존 wrapper의 오류 정책을
   일괄 변경하지 않았으므로 전체 CUDA API의 오류 의미 동등성을 주장하지 않는다.

제품 변경은 [P10-validation-fixes.patch](../patches/P10-validation-fixes.patch)다.
기존 테스트 fixture도 새 `Transport.limits` 초기화 계약, direct-copy 비활성 stub,
재사용 event의 mock 완료 상태 초기화에 맞춰 수정했다. 이 변경은 제품 수정과 구별해
[test-fixture-updates.patch](test-fixture-updates.patch)에 저장했다.

## 실행 결과

| 검사 | 결과와 범위 | 근거 |
|---|---|---|
| 전체 빌드·링크 | Guest shared library, Worker 2종 및 모든 의존 target PASS | [최초 빌드](build.log), [최종 빌드](build-final.log) |
| CPU 경로 검사 | queue gather/bounds/borrowed ownership, socket/memfd/eventfd IPC, owner thread/PID fence PASS; Python 19 tests PASS | [cpu.log](cpu.log) |
| CUDA 모의 검사 | native memset ON/OFF·구 Worker 거절·오류/재시도 금지, pinned pool 재사용/상한/eviction/실패 PASS | [cuda-mock.log](cuda-mock.log) |
| 기존 Broker/cache/ABI 회귀 | 45 tests PASS; 마지막 Guest 변경 후 관련 40 tests 재검사 PASS | [regression.log](regression.log), [최종 회귀](regression-final.log) |
| 기존 C 회귀 | 포인터/복사/커널 descriptor/메모리 오류/소유권/queue, async staging ON/OFF 실패 처리 PASS | [legacy-cuda.log](legacy-cuda.log) |
| layout 권한 | 6 tests 중 4 PASS, root 필요 2 SKIP | [layout-permissions.log](layout-permissions.log) |
| CPU ASan + UBSan | queue, IPC socket/eventfd, owner 및 owner PID 추가 검사 PASS | [sanitizers.log](sanitizers.log), [owner](owner-final-sanitizers.log) |
| IPC 오류 주입 + sanitizer | 잘못된 magic/version/sequence/mode/길이/reserved, 잘린 payload, 출력 canary, event count 오류·선행/지연 알림·peer 사망·20초 deadline·unsealed memfd 거절 PASS | [ipc-failures.log](ipc-failures.log) |
| 실제 GPU 정확성 | 기본값·단일 기능·누적 적용 19조건 PASS; last-error 수정 영향 P0 포함 10조건 재검사 PASS | [초기 2조건](host-gpu-smoke-v3/results.json), [추가 17조건](host-gpu-matrix/results.json), [최종 P0 재검사](host-gpu-final-memset/results.json) |
| Broker/session 수명 | 기본 경로와 전체 옵션 경로에서 busy 거절, idle heartbeat, 10회 재연결/EOF/CLOSE, 이전 arena 분리, FD 증가 없음, CUDA 자식 사망 후 cache fencing·다음 세션 복구 PASS; owner 경로 30초 부분 패킷 deadline/복구 PASS | [lifecycle](host-gpu-lifecycle/results.json), 각 `*-probe.json` |
| native 오류 상태 | 실제 libcudart 참조와 즉시 오류·오류 후 memset 성공 의미 대조; Guest TLS 검사 PASS | [native 참조](native-sticky-error-reference.json), [Guest](native-error-state.log) |
| 패치 재현 | 지정 순서로 P1~P10 적용 시 runtime 80파일 byte-identical | [patch-replay.json](patch-replay.json) |

각 GPU 조건에서는 동기/비동기 H2D·D2H·D2D 18개 조합을 검사했다. 크기는 0, 1,
16 MiB−1/16 MiB/16 MiB+1, 16,793,604, 32 MiB/32 MiB+1, 128 MiB+1이다.
비균일 데이터 SHA-256, offset, 이벤트 완료와 두 stream, 140회 연속 비동기 enqueue를
확인했다. memset은 7개 크기 × 3개 값으로 21회, 결과와 양쪽 canary를 검사했다.
읽기 전 명시적 완료를 기다렸다. 최초 19조건에서 복사 342개·memset 399개 사례다.
수정 후 P0 포함 10조건을 동일 사례와 sticky-error 검사로 다시 실행했다.
종료 후 테스트 Worker/자식과 slot marker가 정리되고 GPU 0 메모리가 0 MiB로
돌아왔음을 확인했다. [cleanup.json](cleanup.json)에 최종 상태를 기록했다.

초기 실패 로그는 보존했다. `cuda-mock-initial-failure.log`는 응답 상태 초기화 문제,
`regression-initial-failure.log`는 fixture 초기화 계약 문제다. `host-gpu-smoke`는
초기 harness에서 HAMi 필수 환경을 빠뜨려 Worker guard가 거절한 기록이고,
`host-gpu-smoke-hami`는 기존 OFF 경로가 지역 검증 오류를 last-error에 기록하지
않는데 ON과 같은 상태를 기대했던 probe의 실패다. OFF 동작은 별도로 기록했다.

## 재현과 남은 범위

CPU: `bash tests/run_cpu.sh`. CUDA mock: CUDA 12.8 헤더 환경에서
`CUDA_ROOT=/usr/local/cuda bash tests/run_cuda_mock.sh`.
GPU harness는 `tests/host_mapping.c`를 shared library로 빌드하고 CUDA 의존 라이브러리를
`validation/cuda-libs`에 둔 후 `python3 tests/run_host_gpu.py --gpu GPU-… --output NEW_NAME`으로
실행한다. `--probe lifecycle --only baseline-bulk cumulative-P7a`는 수명 검사를 실행한다.
출력 디렉터리는 새 이름이어야 한다. harness는 대상 GPU에 compute process가 있거나
로컬 slot 0 marker가 있으면 시작하지 않는다. 파일 lock은 이 harness끼리만 조정하며
다른 스케줄러에 대한 GPU 예약을 대신하지 않는다.

이번 결과는 호스트 경로의 기능 검증이다. 실제 VM/ivshmem 연결, VM 재생성·세대 전환,
전체 syscall 실패 주입, GPU sanitizer, 장시간 동시성 부하, memset 뒤 검증 kernel과
비기본 stream 의미의 전체 조합은 추가 검증 범위다. P6a 대기 profile 비교와 독립 VM
5회 반복 성능 캠페인, 새로운 Flyt 대조군도 아직 수행하지 않았다. probe의 소요시간은
정확성 검사 기록이므로 성능 개선 수치로 사용하지 않는다. 운영 반영 전 실제 VM
통합 및 필요한 워크로드 회귀 검증을 거쳐야 한다.
