# VMWeave v0.5.10: legacy Conv2d와 작은 CNN 학습

Guest/Worker의 기존 공유메모리 library command 경로에 Conv2d forward와
입력·가중치 backward 중계를 추가했다. 작은 CNN의 ReLU·MaxPool·Linear,
cross-entropy·SGD 조합도 검증했다. 네트워크 RPC나 CPU fallback을 추가하지 않는다.

## 배포 단위와 설정

- Operator chart **0.5.10**, Runtime **v0.5.10 Guest/Worker 쌍**.
- 선택적 내부 Kubernetes Device Plugin chart **0.1.2**와 해당 Guest/workload 이미지.
  스케줄링 계약은 동일하며 설치한 Guest의 hash로 `librarySHA256`을 갱신한다.
- 기존 VM의 Guest package, immutable GPUProfile/Request/Channel, workload initContainer의
  Guest image도 함께 갱신해야 한다. Helm upgrade만으로 이 항목들이 바뀌지는 않는다.
- CRD·RBAC·할당량·namespace·TLS 계약 변경은 없다.
- CNN은 import 전에 다음 설정을 명시한다. 기본 graph 경로로 자동 fallback하지 않는다.

```sh
export TORCH_CUDNN_V8_API_DISABLED=1
```

`torch.backends.cudnn.enabled=True`, `benchmark=False`, FP32 contiguous NCHW,
groups=1, dilation=1, TF32 off 조건을 검증했다. MLP/LSTM의 기존 기본 경로에는
이 CNN 설정이 필요하지 않다.

기존 VM 갱신은 [paired runtime 업데이트 절차](release-v0.5.9.md)를 따른다.
GPU 작업 종료 → Guest package 검증·설치 → 정상 VM 종료와 Channel 회수 → 새 버전
Profile/Request/Channel 생성 → VM 시작 → Plugin hash/image 갱신 → GPU 검증 순서다.
기존 Profile/Request는 롤백용으로 보존하고 finalizer를 강제로 제거하지 않는다.
기본 graph 경로의 CNN 실패를 해결한 릴리스로 해석하지 않는다.

## 검증 근거

- [Conv2d forward](../../experiments/cnn-forward/results/20261113-vm/REPORT.md): GPU198개 결과, MLP/LSTM 회귀.
- [Conv2d backward와 SGD](../../experiments/cnn-training/results/20261113/REPORT.md): GPU216 step/1,302개 텐서,
  입력·가중치 gradient 분리, bias, gradient 누적, 새 Pod 반복.
- [작은 CNN 조합 학습](../../experiments/cnn-model/results/20261113/REPORT.md): GPU80 step/1,040개 텐서,
  합성 입력과 MNIST80개 샘플, 수동 역전파·SGD를 이용한 독립 검산.

위 자료는 게시 전 후보 binary의 검증이다. 후속 [공개 배포물 검증](../../deploy/releases/evidence/v0.5.10/README.md)에서
게시된 Guest/Worker로 CNN80 step/1,040개 텐서와 MLP/LSTM 회귀를 다시 확인했다.
[릴리스 JSON](../../deploy/releases/v0.5.10.json)과
[Plugin0.1.2 기록](../../deploy/releases/device-plugin-v0.1.2.json)에 공개 digest·Guest hash·실제 적용 상태를 기록했다.
현재 공개 버전의 판정은 [current.json](../../deploy/releases/current.json)을 따른다.

기본 cuDNN graph, BatchNorm, AMP, NHWC, grouped/dilated convolution, autotuning Find,
ResNet/YOLO 전체 모델, 정확도 수렴, 실제 규모의 처리량 비교는 지원·검증 범위 밖이다.
기존 GPU diagnostic `abs/max` 표현식 실패도 해결했다고 주장하지 않는다.
