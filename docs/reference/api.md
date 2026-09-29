# CUDA API와 SHM 계약

API export 여부만으로 전체 CUDA 또는 PyTorch 호환성을 판단하지 않습니다.
구현 계약은 코드 옆 문서를 원본으로 관리합니다.

| 참조 | 내용 |
|---|---|
| [현재 API 지원 계약](../../runtime/shm/API_SUPPORT.md) | 메모리 조회, OOM, 학습 opt-in, 요청별 추적 |
| [SHM 계약](../../runtime/shm/shm-contract/README.md) | ABI, descriptor, 세션·채널 계약 |
| [CUDA 실행 코어](../../runtime/shm/cuda-dispatch/README.md) | transport와 분리된 실행 계층 |
| [SHM 큐](../../runtime/shm/shm-queue/README.md) | request/response와 payload |
| [초기 호환성 범위](../../experiments/shm-compatibility/README.md) | 개발 단계 당시 범위; 후속 학습 확장은 API 계약 참고 |

## 주요 경계

- 기본 메모리/device, stream/event, 제한된 async 복사, 명시적 PTX launch를 구현했습니다.
- 고정 PyTorch 학습 경로에 fatbinary 등록·packed 인자와 device VA mirror opt-in을 추가했습니다.
- cuBLAS FP32 SGEMM 경로와 cuDNN handle/version 등 제한된 기능을 다룹니다.
- 전체 Graph 연산·cuDNN 연산·다중 장치·NCCL/DDP는 지원 범위가 아닙니다.

## 진단 설정

`FLYT_TRACE_REQUESTS=1`은 Guest/Worker 요청의 네 지점을 기록합니다.
성능 실험에서는 추적과 별도 로그 I/O의 조건을 명시해야 합니다.
`FLYT_MIRROR_DEVICE_VA=1` 학습 경로의 제약과 환경변수는 API 지원 계약을 따릅니다.

현재 구현의 라이브러리·환경변수 이름은 기존 식별자를 유지합니다.
