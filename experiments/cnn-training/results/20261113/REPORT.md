# Legacy Conv2d backward·최소 학습 검증 — 2026-11-13

**입력·가중치 backward 중계를 추가한 후보에서 최소 Conv2d 학습 검증을 통과했다.**
216개 GPU step의 1,302개 출력·loss·gradient·갱신 파라미터가 CPU 참조와 일치했다.
기존 forward·MLP·LSTM 회귀를 포함한 1,492개 GPU 텐서의 독립 재검산도 통과했다.
이는 명시적 legacy FP32 경로의 기능 검증이며 실제 CNN 모델 규모의 성능 결과가 아니다.

## 변경 내용

- `library_conv_backward.py`에서 `0x3334..0x333b` 8개 command를 생성한다.
  backward-data/filter별 algorithm max count, heuristic, workspace 조회, 실행이다.
- 기존 공유메모리 library command 전송을 사용한다. 네트워크 RPC, 새 서버,
  packet/schema 변경, CPU fallback, 자동 재실행은 추가하지 않았다.
- Data와 Filter API의 서로 다른 인자 순서를 공통 x/w/y descriptor 슬롯으로 변환한다.
  Worker는 descriptor 타입·shape·수명, allocation 범위·offset 및 workspace 요구량을
  확인하고 native cuDNN을 호출한다. native 오류는 caller에 전달한다.
- bias gradient는 PyTorch autograd의 reduction 경로로 계산됐다.
  `cudnnConvolutionBackwardBias` API 자체를 추가한 것은 아니다.

## 환경과 범위

시험 VM은 `vmweave-test-b/dp-dev-20261105`, host는 `gpu-4`다.
단일 client, HAMi cores=25, memory=1024MiB 조건을 유지했다. 다른 control-plane VM은
시험 대상에서 제외하고 전후 UID/spec를 비교했다.

- 공식 이미지: `docker.io/pytorch/pytorch@sha256:eee11b3b3872a8c838e35ef48f08b2d5def2080902c7f666831310ca1a0ef2be`
- 실행 버전: PyTorch `2.11.0+cu128`, CUDA 12.8, cuDNN 9.8.
- 후보 Guest SHA256: `8715f4dd369a4783cbbc4f33f0d4b9e4bc5cae238387adc962df58f3fc4fc1f7`
- 후보 Worker: `localhost/vmweave-worker@sha256:3160d982083b45d47b5c81cdb0899798b838f20f59175320a4de631b599828f2`
- FP32 contiguous NCHW, 입력 `[2,3,8,8]`, Conv2d 3→4, kernel 3, groups=1,
  dilation=1. 합성 입력·target, MSE, SGD lr=0.01, seed=20261113.
- `TORCH_CUDNN_V8_API_DISABLED=1`, cuDNN enabled, benchmark=False, TF32 off.
  각 stream은 동일 초기 상태에서 시작한다. 기본·명시적 stream을 순차 검증했다.
- 비교 허용 오차는 모든 실행에서 `rtol=1e-4, atol=1e-6`으로 고정했다.

## 결과

| 실행 | GPU step | 비교 텐서 | Data 호출 | Filter 호출 | 결과 |
|---|---:|---:|---:|---:|---|
| input-v2: 입력 gradient만 | 6 | 30 | 6 | 0 | PASS |
| weight: 파라미터 gradient만 | 6 | 36 | 0 | 6 | PASS |
| minimal: 전체 gradient와 SGD | 6 | 42 | 6 | 6 | PASS |
| matrix: 16조건 | 96 | 576 | 96 | 96 | PASS |
| matrix-repeat: 새 Pod | 96 | 576 | 96 | 96 | PASS |
| accumulate: 두 backward 후 SGD | 6 | 42 | 12 | 12 | PASS |
| 합계 | 216 | 1,302 | 216 | 216 | PASS |

16조건은 bias on/off × stride1/2 × padding0/1 × deterministic on/off다.
각 조건에서 2개 stream × 3 step을 실행했다. 입력 gradient만 계산하는 조건은
optimizer를 실행하지 않으며 파라미터가 바뀌지 않는지도 확인했다.
나머지는 각 step마다 SGD가 실제 파라미터를 변경했음을 확인했다.
accumulate는 같은 입력·target의 두 loss를 합산하는 경우이며 평균으로 나누지 않는다.

저장한 CPU autograd 참조와 GPU 텐서의 최대 절대 오차는 `4.76837158203125e-7`이다.
Worker 로그의 실행별 차이도 표의 Data/Filter 수와 정확히 일치한다.
성공 학습 실행의 forward는 총 222회다. diagnostic 실패의 forward/Data 각 1회를
분리해 계산했으며 성공 횟수에 포함하지 않았다.

회귀 검사도 모두 통과했다.

| 회귀 | 검증 결과 |
|---|---|
| 기존 legacy forward matrix | 96개 GPU 결과 일치 |
| 기본 Lt MLP 5-step | 22개 텐서 일치 |
| 기본 LSTM 5-step | 36개 텐서 일치 |
| 새 Pod LSTM 반복 | 36개 텐서 일치 |
| 후보 basic 후속 실행 | PASS, client 회수 후 재사용 |

MLP/LSTM은 Lt 또는 cuDNN을 끄지 않고 기존 기본 실행 경로를 사용했다.
최종 후보 Worker 로그는 forward319/Data217/Filter216이다. 이 수에는 기존 forward
회귀96회와 diagnostic 실패의 forward/Data 각1회가 포함된다. library trace의
native 반환 코드는 모두 성공이었다.

## 독립 재검산과 호스트 검사

`audit_tensors.py`는 저장한 초기 입력·target·가중치에서 참조를 다시 만든다.
Conv2d gradient는 autograd backward를 재호출하지 않고 unfold/matmul/fold 수식으로
계산하며 SGD도 수동 갱신한다. 저장된 CPU 및 GPU 결과를 이 참조와 비교했다.
기존 회귀의 raw tensor 비교까지 합해 **1,492개**를 검사했다.

- CNN 학습의 명시적 수식 참조 대비 최대 절대 오차: `3.5762786865234375e-7`.
- 전체 감사의 최대 절대 오차: `3.516674041748047e-6` (LSTM, 지정 상대 오차 내).
- 감사에만 로컬 `2.11.0+flyt.cu128`의 CPU 기능을 사용했다. GPU 실행은 모두 위의
  공식 이미지이며 감사 환경과 구분한다.
- codegen check, CMake 빌드, library wire/Guest/forward/backward 검사,
  SHM training 및 path optimization host 회귀를 통과했다.
- Worker backward ASan/UBSan 검사는 통과했다. Guest sanitizer 최초 두 실행에서는
  `AddressSanitizer:DEADLYSIGNAL`이 발생했고 상세 로그는 초기화 출력에서 끝났다.
  같은 PIE binary의 후속 3회 및 `-no-pie`로 빌드한 동일 소스의 3회는 통과했다.
  최초 종료 원인은 확정하지 않았으며 실패 로그도 보존했다. runtime binary를
  수정해 우회한 것은 아니다. 호스트의 mocked execution 검사는 GPU 판정을 대신하지 않는다.

## 실패 기록과 검사 도구 수정

1. `forward-only-baseline`: 새 namespace 직후 default ServiceAccount가 아직 없어
   Pod 생성이 거부됐다. 학습은 실행되지 않았다. runner에 ServiceAccount 생성 대기를
   추가하고 별도 Pod/디렉터리에서 재실행했다.
2. `forward-only-baseline-retry`: 이전 forward 전용 Guest/Worker에서는 GPU forward가
   완료된 뒤 첫 backward에서 SIGSEGV(-11)가 발생했다. CPU 3-step은 완료됐고 loader
   trace에서 convolution backward API가 native cuDNN에 바인딩된 기록을 보존했다.
3. `candidate-input`: 새 후보에서 Data backward와 stream 동기화는 완료됐지만,
   검사 코드의 `inp.grad.abs().max().item()` GPU 표현식에서 SHM CUDA error가 발생했다.
   정확한 하위 CUDA 호출 원인은 이번 범위에서 규명하지 않았다.
4. 이후 probe는 gradient를 CPU로 저장한 뒤 비영 여부를 확인하도록 수정했다.
   모델 forward·MSE·backward·SGD 실행 위치는 GPU로 유지했다. 수정된 input-v2 및
   전체 학습이 통과했고 raw gradient의 독립 수식 검산도 통과했다.

이 때문에 임의의 GPU reduction 연산까지 포괄적으로 지원한다고 주장하지 않는다.
실패 실행의 코드·상태·로그와 수정 후 코드는 각 디렉터리에 별도로 남아 있다.

## 복원과 재현

정상 VM 종료와 Channel 회수 절차를 사용해 기존 공개 v0.5.9 Guest/Worker,
Device Plugin0.1.1 구성으로 복원한다. finalizer 강제 삭제나 수동 SHM 삭제를 사용하지 않는다.
복원 후 공개 Guest를 사용하는 basic GPU probe, idle broker, 원래 VM/Channel spec,
기존 Profile/Request/PVC의 UID/spec, Plugin values, 보호 VM/VMI의 UID/spec를 확인한다.
최종 복원·정리 판정은 `restoration.json`과 `regression/restored-published-basic`에 기록한다.

최종 결과는 **PASS**다. VM은 Always/Running/Ready, Channel은 Ready이며 broker는
activeClient=false다. 공개 Guest SHA256은
`3b3644f42ae3d075c08c22e2578e59553e29c5a446f65cf41f33ad68a070a4a9`이다.
공개 Worker는 `ghcr.io/woogiboogi1129/vmweave-worker@sha256:efb17db71fbf9e1b497fce5cdd60e7a121d5e5d25d470bfda44cc38b34f926ca`다.
위 전후 비교와 복원 후 GPU probe가 통과했고, 시험 namespace 3개·빌드 helper Pod·
baseline/candidate Profile 및 Request를 모두 정리했다.

```sh
python3 experiments/cnn-training/validate.py
# CPU PyTorch 환경에서 raw tensor 감사
python3 experiments/cnn-training/audit_tensors.py
```

`artifacts.json`은 결과 파일 hash, `candidate-artifact-identity.json`은 binary·source
hash를 기록한다. `source/`에 실행 시점 소스를 보존했다. 연결 자격증명은 결과에 포함하지 않는다.

## 다음 단계의 경계

이번에 확인한 것은 **작은 단일 Conv2d의 backward와 SGD 기능**이다. 기본 cuDNN graph
경로의 지원을 추가하지 않았고 이전 단계의 SIGSEGV를 해결했다고 주장하지 않는다.
BatchNorm·AMP·NHWC·grouped/dilated convolution·autotuning Find·ResNet·YOLO,
실제 데이터셋 정확도 수렴 및 처리량 비교는 아직 검증하지 않았다.
다음 기능 단계는 여러 Conv와 activation/pooling/Linear를 조합한 작은 CNN에서
필요한 미지원 연산을 분리하고 학습을 검증하는 것이다. 공개 릴리스·배포는 수행하지 않았다.
