# 기본 cuDNN·cuBLASLt 경로의 LSTM 학습 검증

2026-11-08, 수정한 VMWeave Guest/Worker 후보에서 공식 PyTorch `nn.LSTM`의
forward, backward, optimizer update, 연속 학습과 체크포인트 재개가 통과했다.
cuDNN은 활성화했고 `DISABLE_ADDMM_CUDA_LT`, `TORCH_CUDNN_V8_API_DISABLED`는 설정하지 않았다.
공식 PyTorch 이미지의 wheel·CUDA 라이브러리는 변경하지 않았다.

## 조건과 판정

- 실제 MNIST의 앞 1,024개 학습 이미지, 앞 256개 시험 이미지.
  원본 URL·hash는 [데이터 manifest](../../data/manifest.json)에 있다.
- 이미지 행을 시퀀스로 변환한 `[batch16, sequence28, input28]`, 단층·단방향 LSTM hidden32와 Linear10.
- FP32, dropout0, TF32 off, cuDNN deterministic, SGD lr0.01, foreach/fused off, seed20261108.
- 내부 Kubernetes의 Device Plugin GPU Pod에서 실행. GPU 예약은 compute25%, memory1024MiB.
- CPU 참조와 비교 기준은 `abs(gpu-cpu) <= 1e-6 + 1e-4*abs(cpu)`이다.
  모든 비교 텐서가 유한함을 별도 CPU 환경에서 다시 확인했다.

| 시험 | 결과 | 비교 텐서 수 | 최대 절대 차이 |
|---|---|---:|---:|
| 실제 이미지 5-step LSTM | 통과 | 36 | 3.516674e-6 |
| 새 Pod의 동일 LSTM 재현 | 통과 | 36 | 3.516674e-6 |
| 배치를 바꾸는 2 epoch / 128 step | 통과 | 7 | 4.470348e-7 |
| step32 체크포인트 → 새 Pod에서 나머지 96 step | 통과 | 7 | 0 |
| 기본 cuBLASLt 경로 MLP 5 step | 통과 | 22 | 4.284084e-8 |
| 후속 기본 CUDA 행렬곱 | 통과 | assert_close | — |

5-step 검사는 step1·5의 sequence, h/c, logits, loss, 입력 gradient,
모든 파라미터 gradient와 갱신된 파라미터를 비교한다.
연속 학습은 최종 가중치와 검증 logits를 CPU와 비교하며, 재개 시험은 중단 없이 실행한
GPU 결과와 비교한다. SGD에 momentum이 없으므로 복잡한 optimizer 상태의 복원까지 검증한 것은 아니다.
원시 `.pt` 파일을 별도 PyTorch 2.6.0+cpu 환경에서 다시 비교한
[독립 검산](offline-tensor-audit.json)도 108개 텐서 모두 통과했다.

학습 첫 loss는 2.3459923, 마지막 GPU loss는 2.2934217이었다.
CPU·GPU의 검증 loss는 모두 2.3007512, 정확도는 모두 **9.375%**다.
이번 짧은 시험은 학습 연산의 실행·정확성·지속성 검증이며, 분류 모델의 유의미한 수렴을 입증하지 않는다.

## 최초 실패와 수정

1. [기존 경로](baseline-lstm/)는 LSTM을 CUDA로 이동하면서 SIGSEGV(signal11)로 종료됐다.
2. cuDNN tensor/dropout/RNN/RNNData descriptor, RNN v8 가중치·workspace 조회,
   forward 및 data/weight backward 중계와 cuBLASLt FP32 중계를 추가했다.
   [v2](candidate-v2-lstm/)는 LSTM forward 이후 Lt heuristic 단계에서 실패했다.
3. PyTorch가 cuBLAS handle을 Lt 연산에 사용하는 alias 경로를 연결한
   [v3](candidate-v3-lstm/)는 head/loss까지 진행했으나 backward의 임시 공간 조회에서 실패했다.
4. `cudnnGetRNNTempSpaceSizes`의 workspace/reserve 출력 포인터가 각각 생략 가능하도록
   Guest 검증을 수정한 v3b에서 학습이 통과했다. Worker 바이너리는 v3와 동일하다.

각 실패의 종료 상태·stdout/stderr·Pod 선언을 보존했다. 시험 VM 준비 중 발생한
이미지 digest·네트워크 및 Worker 교체 문제는 [준비 기록](preparation-events.json)에 별도 기록했다.
사라진 v2 Worker 로그를 재구성하지 않았으며, v2의 실패 단계는 보존된 클라이언트 기록을 따른다.

## 실제 GPU 경로의 근거

[Worker trace](final-worker.log)에 RNN forward(`0x3314`), backward data(`0x3315`),
backward weights(`0x3316`), Lt matmul(`0x3322`)의 실제 호출과 성공 반환이 있다.
[학습 중 GPU 관측](continuous-gpu-observation.json)은 Worker 세션 PID292가
호스트 PID1931914와 동일한 프로세스임을 NSpid로 연결하고, GPU 메모리716MiB를 확인했다.
CPU fallback으로 실행한 결과가 아니다.

- PyTorch: `2.11.0+cu128`, 공식 이미지
  `docker.io/pytorch/pytorch@sha256:eee11b3b3872a8c838e35ef48f08b2d5def2080902c7f666831310ca1a0ef2be`.
- 후보 Worker:
  `localhost/vmweave-worker@sha256:fd06615ddb041284497fa6365920ba353ad316f9a10cfc63741b32d2a9195a48`.
- 후보 Guest SHA256:
  `70eb40667137efde888cc530d15e6332361df6dc0f396522b81a44827a3165f8`.
- [Worker 바이너리 hash](worker-binary-sha256.txt), [실험 소스 hash](source-manifest.json),
  각 시험의 `submitted.json` 및 `guest-adapter.txt`를 보존했다.

## 구현 범위와 회귀 검사

새 라이브러리 RPC는 타입별 descriptor ID와 allocation handle+offset을 사용하며,
Worker에서 포인터 범위를 확인한다. RNNData FP32·unpacked·batch≤1024, tensor rank≤8,
Lt FP32 host scalar·열 우선 layout 및 기본/bias epilogue로 범위를 제한했다.
Lt algorithm/heuristic 구조체 전송은 CUDA12.8 x86-64 ABI에 한정한다.
다른 모델 크기·RNN/GRU 변형·AMP·CNN·분산 학습·다른 라이브러리 버전은 이번 실험으로 검증하지 않았다.

컨테이너 build stage에 새 RPC 검사를 포함했다. 패킷 길이, descriptor round-trip,
잘못된 타입·stale handle, 미지원 형식, 자원 정리, 선택적 출력, 잘린 응답 처리가 통과했다.
기존 SHM 학습·CUDA mock 경로 검사와 전체 build stage도 통과했다.
로그는 `library-regression.log`, `shm-regression.log`, `path-regression.log`,
`container-build-validation.log`에 있다.

이 결과는 저장소의 **후보 구현**을 검증한다. 공개 v0.5.8 이미지에 반영하거나 배포한 결과가 아니다.
진단 trace를 활성화했으며 통신 오버헤드·처리량 비교를 수행하지 않았다.
범용 VM 서비스라는 주장에는 추가 workload와 수렴·장시간·동시 실행 검증이 필요하다.

## 회수와 재검증

시험 종료 후 세션 자식 프로세스와 GPU compute process가 없는 것을
[관측](idle-gpu-observation.json)했다. 임시 내부 namespace와 후보 VM·Profile·Request·Channel·Service,
빌드용 Pod를 제거하고 기존 VM의 Halted 상태와 Channel의 Stopped 상태를 복구했다.
기존 root/SHM PVC는 유지했다. 기존 객체 UID·설정 일치 검사는
[cleanup.json](cleanup.json)에 기록했다. Controller가 생성하는 SHM 세대·할당 정보와
cloud-init의 layout marker만 비교에서 제외했다.

```sh
python3 experiments/rnn-default/validate.py
python3 experiments/rnn-default/audit_tensors.py
```

첫 명령은 보존된 성공·실패 판정, 기본 경로 설정, GPU 연결 근거, 회수 및 SHA256을 검사한다.
두 번째는 PyTorch가 설치된 CPU 환경에서 원시 텐서의 유한성·정확성을 다시 계산한다.
