# 잔여 경로 비용에 대한 후속 변경안

2026-10-27. 이 문서는 다음 후보의 설계 제안이며, 아래 변경을 현재 후보나 운영 시스템에 적용한 것은 아니다. 최종 측정 수치와 승격 판정은 `REPORT.md`를 참조한다.

## 0. 변경 전: 큰 payload 경로의 구간별 비용 확인

이번 결과는 H2D/D2H 경로의 병목을 보여 주지만 각 memcpy의 배타적 시간을 측정한 것은 아니다.
별도 진단 build에서 Broker의 arena→SHM, Worker snapshot, snapshot→child arena,
D2H child arena→부모 output, response publication, Guest-side response snapshot을 각각 계수한다.
특히 Guest의 BAR read에 사용하는 bounded word snapshot과 Flyt의 memcpy 차이를 확인한다.
같은 프로세스의 monotonic clock으로 구간을 재고 byte/call 수를 함께 남긴다.
기존 receive/exchange 지표는 대기를 포함하므로 서로 더해 배타적 시간처럼 해석하지 않는다.
진단값은 정식 성능 표본과 분리한다. 아래 1번은 작은 변경으로 먼저 준비할 후보이며,
실제 우선순위는 이 계측으로 확인한 병목에 따라 조정한다.

## 1. 첫 코드 후보: host 부모/자식 사이의 추가 payload 복사 제거

현재 P4는 소켓을 통한 큰 payload 전달을 memfd로 바꿨지만, H2D의 Worker private snapshot → child arena 복사와 D2H의 child arena → 부모 output 복사는 남긴다. `worker_sessions.c`의 `worker_take_into` 및 `session_ipc.c`의 `vmweave_ipc_call`이 변경 지점이다.

- H2D: metadata는 부모의 private 저장소에서 한 번 검증하고, **payload만** host-only arena로 직접 snapshot하는 입력 API를 설계한다. 기존 `request_release`에 borrowed storage를 넘기지 않는다. session envelope·copy descriptor·payload의 offset을 명시하고, 자식과 공유한 metadata를 검증 후 다시 읽는 경로를 만들지 않는다.
- D2H: 자식의 응답 descriptor를 private snapshot으로 검증한 뒤, 유효 길이의 child arena를 `worker_respond`의 입력으로 사용한다. 중간 부모 output 버퍼 복사를 없애되 host arena → VM SHM 복사는 유지한다.
- 요청 완료/응답 publication까지 arena 소유권을 유지한다. 오류·timeout·자식 사망 뒤에는 재사용하거나 재전송하지 않는다. 기존 소켓 경로와 opt-in 비교를 유지한다.

검증: 0/1B, 1MiB±1, 16MiB±1, 마지막 작은 chunk, sequence/length 변조, partial I/O, child death, retained mapping, canary, CPU sanitizer, 실제 VM 세대 전환. 이후 다른 옵션을 고정하고 독립 세션 5회 이상으로 H2D/D2H와 SRAD를 비교한다. 기대 효과의 크기는 구현 전에는 수치로 약속하지 않는다.

## 2. 작은 API와 큰 payload를 분리해서 최적화

`shm-queue/src/queue.c`의 payload snapshot은 정렬된 volatile 8-byte load 반복이다. descriptor를 private로 고정하는 검증 의미와 payload 전송 방법을 분리하여, payload 부분만 bounded vector copy와 비교한다. overread·정렬·페이지 경계·동시 payload 변경 테스트를 먼저 통과해야 한다. 일반 `memcpy`로 일괄 치환해 같은 보장을 가정하지 않는다.

짧은 API에서는 Python Broker, Guest/Broker 소켓, Worker 부모/자식 handshake, polling 대기가 남는다. P5는 C transport owner를 같은 스레드에서 호출하는 변경이며 Python Broker 제거가 아니다. 후속 C Broker는 동일한 socket protocol, busy admission, epoch, heartbeat, cache lease, deadline, fork/EOF fencing을 먼저 differential test로 입증한다.

P6a spin profile은 latency뿐 아니라 Broker·Worker CPU와 장시간 idle 비용을 함께 평가한다. 이번 0/10/50µs 보조 비교는 profile당 VM 1개인 탐색 실험이다. 기본값 변경 근거로 삼으려면 순서를 균형화한 독립 반복을 추가해야 한다.

## 3. 대용량 요청 분할 비용

VMWeave의 현재 16MiB chunk 상한에서는 128MiB+1 전송이 9개 직렬 요청이다. Flyt는 해당 전송을 한 chunk로 처리할 수 있는 더 큰 SHM 영역을 사용한다. 이 차이는 128MiB 결과에 영향을 주지만, 16MiB 이하 차이를 설명하지는 못한다.

먼저 1·16MiB에서 복사/중계 비용을 줄인 뒤, 별도 프로토콜 변경으로 더 큰 협상 가능 arena와 chunk를 검토한다. Guest/Broker/queue/host IPC의 모든 상한, layout 영역, 메모리 quota 및 정수 overflow 검사를 함께 바꿔야 한다. 상수 하나만 키워서는 안 된다. 16/32/64/128MiB 경계의 성능·메모리 비용과 timeout 후 부분 완료 의미를 함께 검증한다.

동시에 여러 chunk를 처리하는 pipeline은 request-id/slot/credit, stream ordering, 부분 실패와 버퍼 수명을 새로 정의하는 P7b다. 이번 후보의 완성된 기능으로 취급하지 않는다.

## 4. P7a의 효과는 비동기 workload에서 별도로 판단

기존 pinned/event pool은 async H2D의 staging 할당을 재사용한다. 이번 정식 Rodinia 및 복사 microbenchmark는 동기 `cudaMemcpy`를 사용하므로 이 pool의 성능 효과를 입증하지 않는다. 실제 VM의 비동기 데이터 정확성 검사는 수행했지만 성능 기여도와는 다른 증거다.

후속에는 같은 크기의 연속 async H2D, 두 stream, event completion, pool 상한/eviction을 포함하여 fresh CUDA session 5회 이상을 비교한다. 반환 지연과 최종 완료시간, pinned 메모리 high-water를 따로 보고한다. synchronous host arena를 pinning하는 방안은 HAMi 메모리 계상 및 CUDA 등록/해제 수명까지 포함한 별도 후보로 검증한다.

## 5. 승격 전 검증 조건

Compute Sanitizer는 현재 HAMi와 함께 실행한 Worker가 readiness 전 단계에서 진행하지 못했다. 두 시도에서 CUDA 검증 kernel을 실행하지 못했으므로 성공으로 처리할 수 없다. 부모/자식 exec와 interposer 초기화를 최소 재현으로 분리하고, 대상 CUDA 자식에 정상 attach되는 방법을 확인한 뒤 다시 실행해야 한다.

이번 비교는 GPU 100%·8GiB, 특정 네 workload 조건이다. 성능 우위가 확인되는 후속 후보에는 실제 운영 quota(50%·2GiB) canary와 사용 중인 응용 회귀 검사가 필요하다. 개별 단계의 전체 성능 ablation, 모든 syscall 실패 주입과 장시간 동시성 부하도 별도 검증 범위다. 새 후보는 기존 Flyt/VMWeave 대조군과 같은 사전 판정 규칙으로 다시 비교한다.

응용에 BAR를 직접 공개하거나 metadata 검증·세션 프로세스 경계를 없애서 속도를 맞추는 변경은 이 개선안에 포함하지 않는다.
