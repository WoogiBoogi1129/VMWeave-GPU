# VMWeave CNN 학습 사전 진단 — 2026-11-07

**기초 CUDA 연산과 CPU CNN 참조는 통과했지만, GPU CNN은 첫 forward에서 SIGSEGV로 종료됐다.**
충돌 경로는 `getCudnnHandle → cudnnSetStream`으로 좁혔다. `cudnnCreate`가 반환하는 VMWeave의
원격 handle을 Guest native cuDNN의 `cudnnSetStream`에 전달하는 중계 누락이 확인됐다.
CNN 계산·역전파·BatchNorm의 GPU 정확성은 아직 검증하지 못했다.

실행 시간은 2026-11-07 15:05–15:09 KST이며, VMWeave VM 하나만 사용했다.
Passthrough·native GPU 비교·성능 측정·런타임 기능 변경은 수행하지 않았다.

## 고정 환경과 범위

| 항목 | 실제 조건 |
|---|---|
| VM / 내부 namespace | `vmweave-test-b/dp-dev-20261105` / `cnn-preflight-20261107` |
| GPU quota | 기존 compute25 / VRAM1024MiB 유지 |
| 공식 이미지 | `pytorch/pytorch@sha256:eee11b3b3872a8c838e35ef48f08b2d5def2080902c7f666831310ca1a0ef2be` |
| PyTorch / CUDA | `2.11.0+cu128` / 12.8, Python 3.12.3 |
| Guest library SHA256 | `32bf53906f6cd4fd681c7af9068aad6274ea8c972c31e57d5efaf009e74e1bc5` |
| Worker image digest | `sha256:e2139218e2abc9efa5b5537e8ca7d7567e5dbbe8bc9a40df42f89820894386ad` |
| 설정 | legacy cuDNN 선택, cuBLASLt 우회, FP32 NCHW eager, deterministic, TF32/benchmark off |
| 입력 / 모델 | `[2,3,8,8]`, Conv2d 3→4, kernel3/stride1/padding1, bias 포함 |
| 학습 참조 | MSE + SGD(lr=0.01, foreach/fused off), 3 step, 입력에도 requires_grad |
| 사전 허용 오차 | rtol=1e-4, atol=1e-6. GPU CNN 결과가 없어 비교 단계 미도달 |

[protocol.json](protocol.json), [실제 Worker](environment/worker.json), 각 Pod의 `submitted.json`과
`pod.json`에 선언·할당·실제 imageID를 보존한다. CPU Pod에는 GPU 자원을 할당하지 않았다.
GPU Pod는 순차 실행했다. 공식 wheel·CUDA 라이브러리·Guest·Worker는 변경하지 않았다.

## 실행 결과

| Pod | 결과 | 실제 도달 범위 |
|---|---|---|
| `cpu-reference` | PASS | Conv forward, Conv 학습 3 step, Conv–BN–ReLU 학습 3 step |
| `gpu-basic` | PASS | CUDA 초기화·H2D/D2H·덧셈·행렬곱 검산 |
| `conv-forward` | FAIL / signal11 | CPU 참조와 GPU 전송 이후 첫 GPU forward에서 충돌 |
| `conv-train` | FAIL / signal11 | 첫 GPU forward에서 충돌, backward/SGD 미도달 |
| `conv-bn` | FAIL / signal11 | 첫 GPU Conv에서 충돌, GPU BN/역전파 미도달 |
| `conv-forward-loader` | FAIL / signal11 | 별도 LD_DEBUG=bindings 실행으로 심볼 제공 라이브러리 수집 |
| `conv-forward-calltrace` | FAIL / signal11 | 진단 interposer로 `getCudnnHandle → cudnnSetStream` 진입 확인 |
| `cudnn-stream-repro` | FAIL / signal11 | 원격 cudnnCreate 성공 후 native cudnnSetStream 호출만으로 재현 |
| `gpu-after-failures` | PASS | 실패 세션 종료 후 새 Pod의 기초 CUDA 검산 |

총 9개 Pod 중 3개 Succeeded, 6개 Failed다. child returncode -11은 supervisor가 Pod exit139로
보존했다. timeout·CPU fallback은 없었다. 실패가 예상된 진단이어도 기능 PASS로 바꾸지 않았다.
마지막 재사용 검증은 기초 CUDA만 대상으로 하며 CNN 복구 성공을 뜻하지 않는다.

CPU 전체 출력·loss·입력 gradient·parameter gradient·갱신 parameter·BatchNorm buffer는
[cpu-reference/](cpu-reference/)의 세 `.pt` 파일에 보존한다. GPU 시험에서도 독립 CPU 참조를
계산해 저장했지만, GPU forward 출력은 생성되지 않았다.

## 최초 실패의 근거

1. [원래 forward 실행](conv-forward/stderr.txt)은 `torch.nn.Conv2d._conv_forward`에서 SIGSEGV로
   종료됐다. 기초 CUDA와 CPU 참조는 이미 통과했다.
2. [loader 기록](conv-forward-loader/loader-filtered.txt)에서 `libtorch_cuda.so`의 `cudnnCreate`는
   `/opt/vmweave/adapter/libvmweave_guest.so`에, `cudnnSetStream`은 Guest의
   `nvidia/cudnn/lib/libcudnn.so.9`에 연결됐다. descriptor와 convolution 함수도 native로 연결됐다.
   loader binding 자체를 모든 함수의 실제 실행 증거로 보지는 않는다.
3. [호출 추적](conv-forward-calltrace/stderr.txt)은 실제 CNN 실행에서 `getCudnnHandle`이
   `cudnnSetStream`을 호출했음을 보여준다. 진단 wrapper는 같은 native 라이브러리로 위임했고,
   진입 기록 이후 반환 기록 없이 SIGSEGV가 발생했다. 이 wrapper는 중계 구현이나 성공 stub이 아니다.
4. [최소 재현](cudnn-stream-repro/stdout.txt)에서도 `cudnnCreate`는 status0을 반환했지만,
   그 handle과 기본 stream을 native `cudnnSetStream`에 전달하자 SIGSEGV가 발생했다.
   이 시험은 `ctypes.CDLL(None)`의 전역 lookup과 PyTorch의 로컬 dependency scope 차이를 고려해,
   loader에서 확인한 native 라이브러리를 명시적으로 조회했다.

현재 [Guest 구현](../../../../runtime/shm/src/guest_compat.c)은 cuDNN create/destroy/version만
중계한다. [Worker 구현](../../../../runtime/shm/src/compat.c)은 실제 cuDNN handle을 Worker 내부에
보관하고 Guest에는 숫자 ID를 반환한다. 이 ID는 Guest native cuDNN 객체가 아니다.

PyTorch 2.11의 [Handle.cpp](https://github.com/pytorch/pytorch/blob/v2.11.0/aten/src/ATen/cudnn/Handle.cpp)는
handle 확보 직후 current CUDA stream으로 `cudnnSetStream`을 호출한다. 관측된 호출 스택과 일치한다.
따라서 우선 해결할 문제는 convolution 알고리즘 선택 이전의 **handle·stream 중계 및 native 혼용**이다.
native 내부의 정확한 fault instruction까지 디버거로 조사한 것은 아니다.

## 추가 발견: cuDNN 버전 차이

CPU Pod의 native cuDNN 조회는 **91900(9.19.0)**, VMWeave GPU Pod의 중계된 조회는
**90800(9.8.0)**이었다. GPU Pod에는 공식 이미지의 native cuDNN도 로드되어 있다.
GPU Pod의 `torch.backends.cudnn.version()`만으로 Guest 라이브러리의 실제 버전을 판단하면 안 된다.

이 차이만을 이번 충돌의 원인으로 확정하지 않는다. 원격 ID를 native handle로 전달하는 문제는
별도로 입증됐다. 다음 구현에서는 Guest header/library와 Worker cuDNN의 호환 범위를 고정하고,
Worker에 없는 새 기능을 지원하는 것처럼 보이지 않게 해야 한다. 이번에는 버전을 교체하지 않았다.

## 다음 구현 목록

| 우선순위 | API/기능 | 근거와 현재 판정 |
|---|---|---|
| P0 | `cudnnSetStream`, 필요 시 `cudnnGetStream` | SetStream은 실제 진입·충돌 관측. 기존 DNN handle과 원격 stream ID를 Worker에서 검증·연결해야 함 |
| P0 | 미지원 cuDNN handle 경로의 명시적 거절·loader 계약 | 현재 일부 호출이 Guest native로 빠짐. 성공 stub 없이 안전한 미지원 오류 필요 |
| P0 | cuDNN 버전/ABI 계약 | Guest native9.19와 Worker 조회9.8 차이를 실제 관측 |
| P1 | tensor/filter/convolution descriptor 생성·설정·조회·해제 | native binding 및 소스상 필요. 이번 GPU CNN에서 성공 여부는 검증하지 않음 |
| P1 | convolution math/group 설정, forward workspace/알고리즘 조회 및 실행 | PyTorch legacy 소스상 후속 필요. 이번 실행은 이 단계 이전에 실패 |
| P2 | backward-data/filter, 필요한 bias gradient 경로 | CPU 참조 확보. GPU 미도달 |
| P2 | BN training/backward 및 workspace/reserve-space | CPU 참조 확보. GPU BN 자체는 미도달 |

후속 API 범위는 PyTorch 2.11의
[Descriptors.h](https://github.com/pytorch/pytorch/blob/v2.11.0/aten/src/ATen/cudnn/Descriptors.h),
[Conv_v7.cpp](https://github.com/pytorch/pytorch/blob/v2.11.0/aten/src/ATen/native/cudnn/Conv_v7.cpp),
[BatchNorm.cpp](https://github.com/pytorch/pytorch/blob/v2.11.0/aten/src/ATen/native/cudnn/BatchNorm.cpp)를
근거로 한 구현 후보이며 모든 API가 이번 실행에서 호출됐다는 뜻은 아니다.

다음 단계의 완료 기준은 **기본/명시적 stream을 대상으로 SetStream 중계와 세션 소유권 검증이
통과하고, 최소 Conv2d가 같은 충돌 대신 다음 지원 경계까지 진행하는 것**이다. SetStream만
구현하고 CNN 전체 학습이 지원된다고 선언하지 않는다.

## 원자료·재현·정리

- [실행기와 시험 계약](../../README.md), [기계 판독 요약](summary.json).
- `sources/baseline-configmap.json`은 최초 실행의 immutable 코드다. 직접 API 시험의 native
  lookup과 호출 추적 추가는 `sources/diagnostic-configmap.json`으로 별도 보존했다.
  앞선 실패를 덮어쓰지 않았고 baseline·diagnostic의 sourceSHA256을 구분한다.
- 진단 interposer 빌드: `cc -shared -fPIC -O0 -g -Wall -Wextra trace_stream.c -ldl -o trace-stream.so`.
  GCC 12.4.0. source와 binaryData 및 SHA256을 보존한다. 설치된 Guest/Worker 파일은 수정하지 않았다.
- [shutdown.json](shutdown.json)과 [restoration.json](restoration.json)에서 15:11 KST에 원래 VM Halted,
  VMI 부재, Channel Stopped를 확인했다. VM/Channel/GPURequest UID와 원래 설정을 유지했다.
  최초 VM spec 원문 비교는 실패했으며, 조사 결과 기동 시 컨트롤러가 갱신한 allocation/generation
  annotation과 cloud-init의 layout 표식만 달랐다. [세션 식별자 변경](vm-session-identity-changes.json)을
  보존하고 이 세 필드의 세션 정보만 제외한 설정 비교를 통과했다. 만료된 식별자를 되돌리지 않았다.
  Channel/GPURequest spec은 원문까지 일치한다.
  전용 namespace에는 완료된 증거 Pod/ConfigMap을 남기고 활성 GPU workload는 없다.
- 오프라인 증거 감사: `python3 experiments/cnn-preflight/validate.py`. 이 감사의 PASS는
  **실패 기록과 복구 증거의 정합성**이며 CNN 학습 PASS가 아니다.
