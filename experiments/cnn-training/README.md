# Legacy Conv2d backward와 최소 학습 검증

VMWeave의 기존 공유메모리 library command 경로에 Conv2d 입력·가중치 gradient
중계를 추가하는 단계다. TCP 통신이나 새 RPC 서버를 추가하지 않는다.
구현은 `scripts/codegen/library_conv_backward.py`에서 생성하며 Guest와 Worker를
같은 소스로 함께 빌드한다. 공개 v0.5.9 릴리스에 포함됐다는 의미는 아니다.
2026-11-13 공식 PyTorch GPU 학습 216 step/1,302개 텐서 및 기존 회귀를 통과했다.
회귀를 포함한 원시 GPU 텐서 1,492개의 독립 재검산도 통과했다.

## 검증 범위

- FP32 contiguous NCHW, groups=1, dilation=1, kernel=3.
- 입력 `[2,3,8,8]`, 출력 채널 4, 합성 입력·target, MSE loss, SGD lr=0.01.
- 명시적 `TORCH_CUDNN_V8_API_DISABLED=1`, cuDNN enabled, benchmark=False,
  TF32 off. 기본 cuDNN graph 경로의 지원을 추가하지 않는다.
- 입력 gradient만 계산, 가중치 gradient만 계산, 전체 gradient 및 bias gradient,
  3-step SGD 갱신을 구분한다. 별도 조건은 두 번의 backward 후 SGD를 수행해
  gradient 누적을 검사한다.
- 전체 matrix는 bias on/off × stride 1/2 × padding 0/1 × deterministic on/off
  16조건이며, 각각 기본·명시적 CUDA stream에서 3 step을 실행한다.
- 모든 학습 연산은 GPU에서 수행한다. 저장·비교·유한값/비영 검사만 CPU에서
  수행하며 `rtol=1e-4, atol=1e-6`을 고정한다. 실패 시 CPU 학습으로 대체하지 않는다.

실제 데이터셋 학습, 정확도 수렴, ResNet/YOLO, BatchNorm, AMP, channels-last,
grouped/dilated convolution, autotuning Find, 성능 비교는 이 단계의 판정 대상이 아니다.
입력 규모는 기능 검증용이므로 실제 CNN 연산 규모의 성능 결과로 해석하지 않는다.

## 실행과 증거

연결 JSON은 기존 runner의 `sshArgv`, `context`, `node`, `brokerGID` 형식을 쓰고,
`namespace`와 `runID`에 `cnn-training-` 접두사를 사용한다. 연결 정보는 `.local/`에 둔다.
runner는 Ready Channel 및 지정한 Worker digest를 확인한다. VM/Worker 배포는
runner에 포함하지 않는다. 각 실행에 새 Pod 이름과 결과 디렉터리를 사용한다.

```sh
python3 experiments/cnn-training/runner/run.py run \
  --connection .local/cnn-training-20261113/connection.json \
  --results experiments/cnn-training/results/<new-run> \
  --name candidate-matrix --backend legacy --case matrix \
  --guest-library <candidate-libvmweave_guest.so> \
  --worker-image <paired-worker-image@sha256:digest>
```

case는 `input-only`, `weight-only`, `minimal`, `matrix`, `accumulate`다.
Pod 제한은 360초, 자식 프로세스 제한은 300초다. Pod 상태·이미지·소스 hash,
초기 입력·파라미터, CPU/GPU step 텐서, 종료 상태, 선택적 loader trace를 보존한다.
`audit_tensors.py`는 초기 상태로부터 unfold/matmul/fold의 명시적 gradient 및
수동 SGD를 계산해 저장된 CPU·GPU 텐서를 재검산한다. Conv2d autograd backward의
성공 플래그만으로 판정하지 않는다.

[2026-11-13 결과와 제한 사항](results/20261113/REPORT.md).
후보 검증 후 기존 공개 런타임 복원과 시험 리소스 정리까지 확인한다.
후속 단계의 두 Conv 블록·ReLU·MaxPool·Linear 및 MNIST 일부 학습 검증은
[cnn-model](../cnn-model/README.md)에 기록한다.
