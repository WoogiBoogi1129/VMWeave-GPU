# Conv2d forward 구현 및 환경 차단 기록 — 2026-11-13

후속 작업에서 환경을 복구하고 [동일 VM의 GPU 검증](../20261113-vm/REPORT.md)을 완료했다.
아래는 복구 이전의 최초 호스트 단계 기록이며 당시 상태로 보존한다.

**결과: 후보 코드 구현·호스트 검증 완료, 실제 VM/GPU 검증 BLOCKED.**
공개 배포·설치·CNN 학습 지원 완료를 주장하지 않는다. 기존 v0.5.9의 SetStream을
재구현하지 않고 filter/convolution descriptor 및 forward 경로를 추가했다.

## 환경 차단

작업 시작 때 시험 VM `vmweave-test-b/dp-dev-20261105`는 화면상 Stopped이며
`spec.runStrategy=Always`, VMI는 Failed였다. 따라서 원래 상태를 Halted 또는
정상 Running으로 가정하지 않았다. Channel은 `Draining/AwaitingDetachEvidence`였다.

- launcher Pod: `virt-launcher-dp-dev-20261105-gq4sq`, 종료 시각
  `2026-11-13T05:16:11Z` (14:16:11 KST), `vmweave.io/detach-observation` finalizer 유지.
- kubelet 메시지: KVM 장치가 healthy하지 않아 allocation에 실패했다.
- Guest attachment: `Mapped/GuestHELLOReceived`; Worker attachment: `Detached/KubeletTerminalWorker`.
- controller의 정상 detach 조건을 충족하지 않아 재시작·paired 후보 적용을 진행할 수 없다.
  장치 오류 메시지는 당시 실패 기록이며 현재 KVM 장치 전체가 고장났다는 판정은 아니다.
- [환경 원본](environment/before-vm.json), [Pod](environment/before-pods.json),
  [Channel](environment/before-sharedmemorychannel.json),
  [attachment](environment/before-channelattachments.json)를 보존했다.

[baseline preflight](baseline-legacy/preflight.json)에서 실행을 차단했다.
`submitted.json`은 준비한 manifest이며 실제 제출됐다는 뜻이 아니다. Pod/namespace를
생성하지 않았고, VM·VMI·Channel·Request·Pod·Attachment의 UID/spec가 작업 전후 동일하다.
Guest 설치 파일의 현재 hash는 VM에 접속하지 못해 미확인이다. 선언된 Worker 이미지는
v0.5.9이며, Nov 7의 SetStream crash를 현 버전의 실패로 소급하지 않았다.

## 변경

- `scripts/codegen/library_conv.py`의 명시적 schema를 기존 generator에 연결했다.
  기존 35 opcode를 유지하고 `0x3323..0x3333`의 17개 API를 추가했다.
- filter/convolution 생성·설정·조회·파괴, group/math 설정·조회, output shape,
  forward algorithm count/heuristic, workspace 조회, 실제 native forward 호출.
- descriptor는 타입이 있는 세션 ID, GPU 버퍼는 allocation ID+offset으로 전달한다.
  FP32/NCHW 및 convolution 조건을 native descriptor에서 다시 확인한다.
- buffer 전체 범위, 정수 곱셈 overflow, workspace 크기·offset, 잘못된/stale descriptor를
  검사한다. 알고리즘 결과는 최대 8개, 필드별 직렬화이며 native 구조체를 복사하지 않는다.
- 응답이 잘렸거나 개수가 범위를 벗어나면 caller 출력 저장소를 변경하지 않는다.
  Worker가 반환하는 오류를 유지하며 CPU fallback이나 알고리즘 재실행을 추가하지 않았다.
- probe는 bias/stride/padding/heuristic 설정 및 stream 조합을 준비했다. 기본 cuDNN
  graph 경로는 별도 진단 대상이며 legacy 성공으로 대체 판정하지 않는다.

## 검증

| 검사 | 결과 | 범위 |
|---|---|---|
| Guest/Worker CMake build | PASS | CUDA 12.8, cuDNN 9.8 builder, GPU 없이 빌드 |
| 기존 library RPC 검사 | PASS | 기존 tensor/RNN/Lt 오류 처리 |
| 새 Worker/Guest RPC 검사 | PASS | 실제 CPU descriptor, scalar/ref/perf encoding, malformed 입력·응답, stream 매핑, 4,096 descriptor 회수 |
| ASan + UBSan | PASS | 새 두 테스트; cuDNN 전역 상태 때문에 leak detection은 제외 |
| 전송·메모리·queue·memset 회귀 | PASS | host/mock 검사; GPU 학습 회귀 아님 |
| CPU probe 자체 검사 | PASS | 16설정, Conv2d와 unfold+matmul 비교, `rtol=1e-4/atol=1e-6` |
| 현재 v0.5.9 GPU stream/forward 진단 | BLOCKED | Channel preflight에서 중단 |
| 후보 GPU forward CPU 비교 96건 | NOT_RUN | 기본·명시적 stream × 16설정 × 3회 |
| 공식 이미지 MLP·LSTM GPU 회귀 | NOT_RUN | 환경 복구 필요 |
| 후보 VM 적용·회수·새 Pod 재실행 | NOT_RUN | 배포하지 않음 |

CPU 자체 검사는 기존 로컬 `PyTorch 2.11.0+flyt.cu128`, Python 3.10 번들이다.
공식 PyTorch 이미지나 새 VMWeave GPU 결과가 아니다. CPU 결과는
`cpu-selfcheck/cpu.pt`, 실행 환경은 [로그](cpu-selfcheck.log)에 있다.
Worker 테스트는 descriptor 구현만 실제 cuDNN을 사용하고 CUDA handle·allocation·execution을
mock했다. 실제 GPU convolution 결과·성능을 측정한 것으로 해석하면 안 된다.

첫 테스트의 `GetConvolutionNdDescriptor(requested=8)` 성공 기대는 cuDNN 9.8의
`CUDNN_DIM_MAX-2` 제한과 달라 실패했다. 정상 조회를 6으로 바꾸고 8의 native
NOT_SUPPORTED 반환을 별도로 검증했다. 기존 host regression 첫 실행의 `libcuda.so.1`
로딩 오류는 테스트용 CUDA stub 경로를 명시해 해결했다. stub은 VM runtime에 배포하지 않았다.

## 남은 완료 조건

VM의 정상 detach 복구 후 공개 v0.5.9 재진단부터 이어간다. 승인된 순서대로 paired 후보를
시험 VM에 적용하고 CPU 수치 비교, Worker 실제 호출, MLP/LSTM 회귀 및 회수·재사용을
검증해야 이번 단계가 완료된다. backward·BatchNorm·ResNet/YOLO 확장은 그 이후 별도 단계다.

API 경로 확인에는 [PyTorch v2.11 Conv_v7.cpp](https://raw.githubusercontent.com/pytorch/pytorch/v2.11.0/aten/src/ATen/native/cudnn/Conv_v7.cpp)와
[NVIDIA cuDNN 9.8 convolution 문서](https://docs.nvidia.com/deeplearning/cudnn/backend/v9.8.0/api/cudnn-cnn-library.html)를 사용했다.
