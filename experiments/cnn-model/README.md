# 작은 CNN의 전체 학습 검증

단일 Conv2d backward 검증 다음 단계다. 기존 공유메모리 후보 런타임으로
Conv→ReLU→MaxPool 블록 두 개와 Linear 분류기의 forward, cross-entropy,
backward, SGD가 이어지는지 확인한다. 런타임 배포와 시험 실행을 분리하며,
실험 후 기존 공개 런타임으로 복원한다.

## 단계와 범위

1. `relu`: Conv2d(3→8)→ReLU, 입력 `[8,3,32,32]`, MSE.
2. `pool`: 위 구성에 MaxPool2d(2)를 추가하고 MSE로 학습한다.
3. `cnn`: Conv(3→8)→ReLU→MaxPool→Conv(8→16)→ReLU→MaxPool→Flatten→Linear(1024→10).
   합성 입력 `[8,3,32,32]`와 정수 라벨로 cross-entropy를 계산한다. 파라미터 11,642개다.
4. `mnist`: 같은 구성을 입력 1채널/28×28, Linear(784→10)로 바꾼다.
   파라미터 9,098개이며 기존 [MNIST fixture](../rnn-default/data/README.md)의
   처음 80개 학습 샘플을 batch16 × 5 step으로 사용한다.

모든 case는 FP32 contiguous NCHW, kernel3/padding1, groups1/dilation1,
SGD lr0.01, seed20261113, TF32 off, cuDNN enabled, benchmark=False다.
명시적 `TORCH_CUDNN_V8_API_DISABLED=1`을 사용한다. 각 기본·명시적 CUDA stream에서
동일 초기 가중치와 5개의 서로 다른 minibatch로 5 step을 실행한다.
전체 CNN과 MNIST는 deterministic on/off도 구분한다.

각 step의 출력·loss·입력 gradient·모든 파라미터 gradient·갱신 파라미터를 저장한다.
CPU와 GPU에서 독립적으로 학습하고 `rtol=1e-4, atol=1e-6`으로 비교한다.
검사·저장만 CPU에서 수행하며 GPU 실패를 CPU 학습으로 대체하지 않는다.
레이어별 forward 완료 지점과 backward/optimizer 완료를 기록한다.

MNIST 일부를 사용한 기능 검사이며 전체 epoch·정확도 수렴 실험이 아니다.
CIFAR-10 크기와 같은 합성 입력을 사용하는 `cnn`도 CIFAR-10 데이터셋 실험이 아니다.
BatchNorm, AMP, 기본 cuDNN graph 경로, ResNet/YOLO, 성능 측정은 범위 밖이다.

## 실행과 감사

```sh
python3 experiments/cnn-model/runner/run.py run \
  --connection .local/cnn-model-20261113/connection.json \
  --results experiments/cnn-model/results/<new-run> \
  --name candidate-cnn --backend legacy --case cnn \
  --guest-library <paired-candidate-libvmweave_guest.so> \
  --worker-image <paired-worker-image@sha256:digest>
```

연결 JSON의 `namespace`와 `runID`는 `cnn-model-` 접두사를 사용한다.
runner는 기존 pinned official PyTorch template과 candidate pair 검사를 재사용한다.
MNIST fixture는 소스 hash와 함께 ConfigMap에 전달한다. Pod 제한480초,
자식 프로세스 제한420초다. namespace 생성 직후 default ServiceAccount를 기다린다.

`audit_tensors.py`는 초기 입력·가중치에서 모든 step을 다시 계산한다. Conv는
unfold/matmul/fold, ReLU는 양수 mask, MaxPool은 저장 index를 이용한 scatter,
Linear는 행렬곱, cross-entropy는 softmax gradient를 사용한다. autograd backward나
optimizer를 호출하지 않고 SGD를 수동 갱신하여 저장된 CPU·GPU 결과를 검산한다.

[2026-11-13 결과](results/20261113/REPORT.md).
증거 검증은 `python3 experiments/cnn-model/validate.py`, 원시 텐서 감사는
CPU PyTorch 환경에서 `python3 experiments/cnn-model/audit_tensors.py`로 실행한다.
