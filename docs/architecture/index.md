# 아키텍처

![데이터와 제어 흐름](../assets/architecture.svg)

## 데이터 경로

1. Guest 중계 라이브러리가 지원하는 CUDA Runtime/Driver 호출을 가로챕니다.
2. 요청은 세션의 request ring과 payload 영역에 기록됩니다.
3. Worker는 요청을 수신하고 CUDA dispatcher를 통해 HAMi/CUDA 경로에서 실행합니다.
4. 결과는 response ring으로 돌아옵니다. 커널 launch 응답과 GPU 완료는 구분합니다.

SHM backing은 GPU 노드의 로컬 파일시스템 PVC와 연결되고 VM에는 ivshmem 장치로 매핑됩니다.
Guest와 Worker는 같은 layout·ABI 및 일치하는 실행 세대를 사용해야 합니다.
이는 GPU 메모리의 일반적인 zero-copy나 PCI 장치 직접 패스스루를 뜻하지 않습니다.

## 제어 경로

Kubernetes API와 admission이 요청 참조·정책을 검사합니다. Channel Controller는
채널 상태를 조정하고 Worker 및 backing의 수명 주기를 관리합니다.
KubeVirt hook의 관리 통신은 유지됩니다. 제거된 것은 기존 CUDA RPC 데이터 경로입니다.

| 구성 요소 | 책임 | 코드 |
|---|---|---|
| Guest library | CUDA interception·요청 직렬화·응답 처리 | [guest.c](../../runtime/shm/src/guest.c) |
| Queue와 계약 | ring·payload·ABI | [큐](../../runtime/shm/shm-queue/), [계약](../../runtime/shm/shm-contract/) |
| Worker·dispatcher | 요청 수신·CUDA 실행·응답 | [Worker](../../runtime/shm/src/worker.c), [dispatcher](../../runtime/shm/cuda-dispatch/) |
| 제어기·admission | 참조 검사·상태·할당·회수 조정 | [control](../../runtime/shm/control/) |
| HAMi | Worker에 적용되는 GPU 자원 정책 | [배포 예제](../../deploy/examples/values-gpu-poc.yaml) |

## Review와 active

`review` 모드는 참조와 상태를 검사하며 SHM 할당·VM 시작·GPU Worker 실행을 하지 않습니다.
`active`는 별도의 실험용 설정과 확대된 권한을 사용합니다. CPU review 성공은 GPU 실행 성공의
대체 근거가 아닙니다. [CPU 설치](../getting-started/cpu-control-plane.md)와
[GPU 준비](../getting-started/gpu.md)를 구분합니다.
