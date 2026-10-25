# 큰 CUDA 복사: 구현 후보

v0.5.3 릴리스 후보 기능이며, 공개된 v0.5.2 이미지/Helm에 포함되었다는 의미는 아니다.
Guest 라이브러리, Guest broker, Worker를 같은 후보 빌드로 사용한다.

## 동작

- `cudaMemcpy`, `cudaMemcpyAsync`, Driver `cuMemcpy{HtoD,DtoH,DtoD}_v2` 및
  `cuMemcpy{HtoD,DtoH,DtoD}Async_v2`에 공통 적용한다. Driver 비동기 함수는
  `cuGetProcAddress`/`cuGetProcAddress_v2`에서도 같은 구현을 반환한다.
- CPU↔GPU의 논리적 복사는 전체 길이를 검증한 다음 순서대로 분할한다.
  한 데이터 청크는 최대 16MiB다. 실제 slot의 요청/응답 arena, 비동기 헤더 56바이트,
  broker의 세션 envelope 24바이트를 반영해 더 작아질 수 있다.
- GPU↔GPU는 전체 길이를 담은 48/56바이트 제어 요청 하나다. 데이터는 GPU에서 복사한다.
- CPU↔CPU는 로컬 `memmove`다. 전송 크기 제한이 적용되지 않는다.
- 전체 device allocation 범위, 주소 overflow, 복사 방향과 device overlap을 먼저 검사한다.
  `cudaMemcpyDefault`의 범위 초과 device 주소를 CPU 주소로 오인하지 않도록 분류와 범위 검사를 나눴다.
- 0바이트 device 복사에도 기존과 같이 유효한 allocation 참조를 요구한다.

## 비동기 수명과 실패

업로드 staging은 완료 event까지 Worker가 소유한다. 세션별 총량은 64MiB, 최대 128개다.
한도를 만나면 이미 제출한 event 완료를 기다리고 회수한 후 다음 청크를 제출한다.
따라서 `cudaMemcpyAsync`도 staging 부족 시 CPU에서 기다릴 수 있다. 한 논리적 호출 안에서는
Guest 공통 lock을 유지하고 같은 stream에 순서대로 제출한다.

DtoH async는 기존처럼 stream 완료와 데이터 반환까지 기다리는 보수적 경로다.
이번 구현은 완전한 비동기 다운로드, pinned/registered host memory API, Unified Memory,
PTDS 또는 CUDA Graph 지원을 추가하지 않는다.

중간 청크에서 실패하면 후속 청크를 보내지 않고 오류를 반환한다. 이미 복사한 앞부분은
되돌리지 않는다. 불확실한 비동기 enqueue/event 실패에서는 Worker 프로세스를 종료하여
진행 중인 staging을 일찍 해제하지 않는다. 기존 세션 장애/캐시 무효화 경로를 유지한다.
64MiB는 **진행 중인 업로드 staging** 한도다. 전체 Worker RSS에는 CUDA context,
요청/응답 버퍼, 라이브러리 등이 추가된다.

## 호환성

새 schema-1 opcode `0x1014` (`VMWEAVE_COPY_LIMITS`)는 빈 요청과 24바이트 응답을 사용한다.
응답은 little-endian `u32 version=1`, `u32 flags`, `u64 H2D chunk`, `u64 D2H chunk`다.
flag 1은 큰 D2D 지원, flag 2는 broker가 실제 전송 한도를 반영했다는 뜻이다.

| 구성 | 결과 |
|---|---|
| 새 Guest + 새 broker + 새 Worker | 큰 복사 지원 |
| 새 Guest가 Worker에 직접 연결 | 실제 slot 용량으로 제한 후 지원 |
| 구 Worker 또는 구 broker가 포함됨 | 기존 16MiB 이하 경로 유지, 큰 복사는 첫 청크 전에 NotSupported |
| 구 Guest + 새 Worker | 구 Guest의 크기 제한 유지 |

지원 여부는 Guest 프로세스에서 한 번 확인한다. 이후 복사는 실제 exchange를 거치므로
기능 정보 캐시가 CUDA 성공이나 세션 생존 여부를 대신하지 않는다. 자동 native/RPC fallback은 없다.
공유메모리 ABI, CRD, 전역 메시지 한도, PTX/module 한도는 확대하지 않았다.

## 검증 및 적용

CPU 회귀 검사는 CUDA 개발 이미지에서 `scripts/test-shm-training.sh <build>`로 실행한다.
`large_copy_guest.c`는 경계·오프셋·오류·구버전·작은 arena,
`large_copy_async.c`는 지연된 event와 staging 압박/실패,
`private_copy_buffers.c`는 실제 실행 adapter의 큰 D2D 범위 검사를 다룬다.
`tests/control/test_guest_broker.py`는 envelope를 반영한 기능 협상을 검사한다.

`tests/integration/large_copy_gpu.py`는 실제 GPU 데이터 검증 도구다.
`--worker` 옵션은 로컬 테스트 연결을 사용하므로 VM/ivshmem 처리량 결과로 해석하지 않는다.
`large_copy_bench.py`의 값은 복사와 완료 동기화의 진단 지연이며 모델 학습 처리량이 아니다.

실제 VM, Rodinia NW/LU, 빌드 식별자와 정리 결과는
[검증 보고서](../releases/v0.5.3-candidate.md)에 기록한다.
릴리스 시에는 세 구성요소를 함께 고정하며, 롤백도 기존 Guest/broker/Worker 조합으로 함께 수행한다.
큰 복사를 수행 중인 세션에서 라이브러리나 실행 파일을 교체하지 않는다.

2026-10-24 후속 작업에서는 주소 분류의 탐색 상한을 마지막 살아 있는 할당까지로 줄였다.
전체 범위 검증은 유지하며, 작은 복사의 성능 게이트와 동일 VM 대조 결과는
[회귀 진단 보고서](../releases/v0.5.3-candidate.md)에 기록한다.
