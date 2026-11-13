# 작은 CNN 전체 학습 검증 — 2026-11-13

**Conv→ReLU→MaxPool 블록 두 개와 Linear 분류기의 전체 학습이 통과했다.**
합성 입력과 MNIST 일부를 사용한 GPU80 step/1,040개 텐서가 CPU 참조와 일치했고,
독립적인 수동 역전파·SGD 검산도 통과했다. 이전 단일 Conv2d backward 후보의
Guest/Worker binary를 그대로 사용했으며 **런타임 수정이나 새 통신 API는 필요하지 않았다.**

이번 결과는 작은 CNN의 실행·수치 정확성을 확인한 것이다. 전체 MNIST 학습의
정확도·수렴, CIFAR-10 데이터셋 실험, ResNet/YOLO 지원이나 성능 개선 결과는 아니다.

## 환경과 변경

- 시험 대상: `vmweave-test-b/dp-dev-20261105`, host `gpu-4`.
- 단일 client, HAMi cores25/memory1024MiB. 보호 control-plane VM은 별도 유지했다.
- 공식 PyTorch `2.11.0+cu128`, CUDA12.8, cuDNN9.8.
- PyTorch 이미지: `docker.io/pytorch/pytorch@sha256:eee11b3b3872a8c838e35ef48f08b2d5def2080902c7f666831310ca1a0ef2be`.
- Guest SHA256: `8715f4dd369a4783cbbc4f33f0d4b9e4bc5cae238387adc962df58f3fc4fc1f7`.
- Worker: `localhost/vmweave-worker@sha256:3160d982083b45d47b5c81cdb0899798b838f20f59175320a4de631b599828f2`.
- legacy 경로를 명시적으로 설정했다: `TORCH_CUDNN_V8_API_DISABLED=1`.
  FP32 contiguous NCHW, kernel3/padding1/groups1/dilation1, TF32 off,
  cuDNN enabled, benchmark=False, SGD lr0.01, seed20261113.

새 workload·runner·수동 검산기·증거 검증기를 추가했다. 기존 공통 runner에는
추가 소스 파일을 ConfigMap으로 전달하는 선택 인자만 추가했다. 이 경로로 기존
MNIST fixture를 전달하며 소스 hash를 함께 기록한다. 공유메모리 전송은 유지했다.
시험 단계는 이전 후보 binary의 조합 학습 범위를 확인하는 것으로, 재빌드하거나
공개 이미지·chart·배포를 변경하지 않았다.

## 모델과 데이터

합성 CNN은 다음 구조다.

```text
[8,3,32,32]
 → Conv2d(3→8, 3×3, padding1) → ReLU → MaxPool2d(2)
 → Conv2d(8→16, 3×3, padding1) → ReLU → MaxPool2d(2)
 → Flatten → Linear(1024→10) → cross-entropy
```

파라미터는11,642개다. 5개의 서로 다른 합성 minibatch를 사용했다. 입력 크기가
CIFAR-10과 같다는 사실만으로 CIFAR-10 학습 실험이라고 부르지 않는다.

MNIST 모델은 입력을 `[16,1,28,28]`, 첫 Conv를1→8, Linear를784→10으로 바꾼
파라미터9,098개의 모델이다. 기존 `experiments/rnn-default/data/mnist.b64` fixture의
처음80개 training 샘플을 /255로 정규화하고 batch16 × 5 step으로 실행했다.
fixture 전체에는 train1,024/test256개가 있으나 이번에는 나머지 샘플과 test set을
사용하지 않았다. fixture SHA256은
`662119a6c5940892f4a3844aed29b9338c8f6aea69a19bf1960473b757115cb7`이다.
원본 파일의 출처/hash는 보존한 `data-manifest.json`을 따른다.

각 stream·deterministic 설정은 동일 초기 가중치와 동일 minibatch 순서로 시작한다.
각 실행의 step마다 출력·loss·입력 gradient·모든 파라미터 gradient·갱신 파라미터를
저장하고, gradient가 존재하며 각 파라미터 텐서가 실제 갱신됐는지도 검사했다.
검사·저장만 CPU에서 처리하며 학습 forward·loss·backward·SGD는 GPU에서 수행했다.
레이어마다 동기화한 진단 실행이므로 시간/처리량 측정으로 사용하지 않는다.

## 결과

| 실행 | GPU step | 비교 텐서 | CPU autograd 대비 최대 절대 오차 | 결과 |
|---|---:|---:|---:|---|
| Conv→ReLU, MSE | 10 | 70 | 5.9604645e-7 | PASS |
| Conv→ReLU→MaxPool, MSE | 10 | 70 | 7.1525574e-7 | PASS |
| 두 Conv 블록+Linear, cross-entropy | 20 | 300 | 2.3841858e-7 | PASS |
| 동일 CNN, 새 Pod 반복 | 20 | 300 | 2.3841858e-7 | PASS |
| MNIST 일부, cross-entropy | 20 | 300 | 2.3841858e-7 | PASS |
| 합계 | 80 | 1,040 | 7.1525574e-7 | PASS |

초기 두 단계는 deterministic=True에서 기본·명시적 stream 각각5 step이다.
전체 CNN과 MNIST는 deterministic on/off × 2개 stream × 5 step이다.
전체 실행의 허용 오차는 고정 `rtol=1e-4, atol=1e-6`이며 실패 후 완화하지 않았다.
이번 학습 실행에는 signal, timeout, 미지원 API 오류가 발생하지 않았다.

Worker trace에서 실제 convolution forward140회, backward-data140회,
backward-filter140회를 확인했다. 실행별 누적 로그의 차이도 모델의 Conv 개수와
step 수에 일치한다. library trace의 native 반환 코드는 모두 성공이다.
후속 basic GPU probe도 통과해 client 종료 후 재사용을 확인했다.

## 독립 검산

`audit_tensors.py`는 저장된 초기 입력·라벨·가중치에서 모든 step을 재계산한다.
autograd backward와 optimizer를 호출하지 않고 다음 수식 경로를 사용한다.

- Conv gradient: unfold, 행렬곱, fold; bias는 합산.
- ReLU gradient: 입력의 양수 mask.
- MaxPool gradient: forward index로 scatter-add.
- Linear gradient: 행렬곱·합산.
- Cross-entropy gradient: `(softmax(logits) - one_hot(label)) / batch`.
- MSE gradient와 SGD도 명시적 수식으로 계산.

저장된 CPU autograd 참조와 GPU 결과 모두 이 참조와 일치했다.
GPU1,040개 텐서의 수동 참조 대비 최대 절대 오차는 `4.76837158203125e-7`이다.
감사에는 로컬 PyTorch `2.11.0+flyt.cu128`의 CPU 기능만 사용했다. 실제 GPU probe의
공식 PyTorch 환경과 구분한다. 원시 텐서와 `tensor-audit.json`을 보존했다.

## 복원과 경계

정상 VM 종료·Channel 회수 절차로 공개 v0.5.9 Guest/Worker와 Device Plugin0.1.1
구성으로 복원하고 공개 Guest의 basic GPU probe를 실행한다. 임시 시험 namespace2개,
candidate Profile/Request만 정리한다. 이 단계에서는 privileged helper Pod를 만들지 않았다.
전후 VM/Channel spec, 기존 Profile/Request/PVC UID·spec, Plugin values 및 보호
control-plane VM/VMI의 UID·spec 비교는 `restoration.json`에 기록한다.

최종 복원 판정은 **PASS**다. VM은 Always/Running/Ready, Channel은 Ready,
broker는 activeClient=false이며 위 전후 비교와 임시 리소스 정리가 모두 완료됐다.
복원 후 공개 Guest의 basic GPU probe도 통과했다. 공개 Guest SHA256은
`3b3644f42ae3d075c08c22e2578e59553e29c5a446f65cf41f33ad68a070a4a9`, 공개 Worker는
`ghcr.io/woogiboogi1129/vmweave-worker@sha256:efb17db71fbf9e1b497fce5cdd60e7a121d5e5d25d470bfda44cc38b34f926ca`다.

기본 cuDNN graph, BatchNorm, AMP, channels-last, grouped/dilated convolution,
ResNet/YOLO와 임의의 GPU 연산 전체 지원을 주장하지 않는다. 이전 단계에서 실패한
GPU diagnostic `abs/max` 표현식을 수정한 것도 아니다. 본 단계의 검사용 reduction은
저장한 CPU 텐서에서 수행했다. 공개 v0.5.9 binary 자체가 CNN 학습을 지원하게 됐다는
의미도 아니다. 검증 대상은 명시된 후보 pair다.

이제 다음 기능 확장 후보는 BatchNorm이 포함된 모델이다. 실제 규모 성능 비교는
그 모델의 학습 정확성·반복 실행이 검증된 뒤 동일 조건의 기준 경로와 비교해야 한다.

## 재현과 증거

```sh
python3 experiments/cnn-model/validate.py
# CPU PyTorch가 있는 환경
python3 experiments/cnn-model/audit_tensors.py
```

`candidate-artifact-identity.json`과 `runtime-source/`는 이전 검증에서 사용한
동일 binary의 소스 기록을 보존한다. 이번 workload·runner·감사 소스는
`workload-identity.json`과 `source/`로 구분한다. `artifacts.json`은 전체 결과 파일의
hash 목록이다. 연결 정보와 자격증명은 `.local/`에 유지한다.
