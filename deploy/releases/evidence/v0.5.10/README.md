# v0.5.10 / Device Plugin0.1.2 공개·배포 검증

**2026-11-13: 게시된 이미지와 Helm chart를 실제 노드에 적용하고 검증했다.**
소스 커밋은 `76ce090f8d5498f8ecd76d77e6fafd173c0e83ef`이며 Runtime/Operator 태그는
`v0.5.10`, Device Plugin 태그는 `device-plugin-v0.1.2`다.

- [Runtime 릴리스](https://github.com/WoogiBoogi1129/VMWeave-GPU/releases/tag/v0.5.10)
- [Device Plugin 릴리스](https://github.com/WoogiBoogi1129/VMWeave-GPU/releases/tag/device-plugin-v0.1.2)
- [Runtime 기록](../../v0.5.10.json), [Plugin 기록](../../device-plugin-v0.1.2.json)

## 게시·적용 내용

| 항목 | 결과 |
|---|---|
| Runtime/Operator 이미지 | operator/helper/hook/worker/guest-artifacts/hami/hami-dra 7종 digest·source label 확인 |
| Operator OCI chart | 0.5.10, 공개 GitHub 자산과 OCI package bytes 일치 |
| Plugin 이미지·OCI chart | plugin/guest/workload 3종, chart0.1.2, portable archive checksum 확인 |
| 중앙 Helm | `vmweave-system/vmweave`, `vmweave-nested-system/nested` → chart0.5.10 |
| 시험 VM | `vmweave-test-b/dp-dev-20261105` Guest/Worker/helper/hook 갱신, Always/Running/Ready |
| 내부 Helm | `vmweave-device-plugin/vmweave-device-plugin` → chart0.1.2, 새 Guest hash |
| GPU 연결 | 새 Profile/Request `dp-dev-20261105-v0510`, 새 Channel binding, Ready |
| 정리 | 시험 namespace 및 임시 관리자 Pod 제거, broker activeClient=false |

공개 Guest 라이브러리 SHA256은
`08ccac5fb763451e448a68700f6156a6e0eba62950614913fb07c62ba966cfa0`다.
Runtime guest-artifacts와 Plugin guest 이미지의 라이브러리 bytes/hash가 일치했다.
후보 빌드의 `8715f4dd...`와 다르므로 공개 이미지로 다시 검증했다.
Worker와 나머지 이미지의 전체 digest는 릴리스 JSON에 고정했다.

Plugin의 portable archive를 Guest CRI store에 가져온 후 image config ID·source label을
원본과 비교했다. 원래 registry reference와 CRI가 다시 계산한 runtime RepoDigest는
Plugin 기록의 `reference`/`runtimeReference`로 구분한다. 실제 Pod·Helm은 검증한
runtime reference를 사용했다. SHA 검사를 하는 initContainer가 공개 Guest image에서
라이브러리를 복사하며 후보 바이너리 ConfigMap을 주입하지 않았다.

## 실제 GPU 검증

공식 PyTorch `2.11.0+cu128` 이미지
`docker.io/pytorch/pytorch@sha256:eee11b3b3872a8c838e35ef48f08b2d5def2080902c7f666831310ca1a0ef2be`를 사용했다.
CNN은 명시적 legacy, FP32 contiguous NCHW, groups1/dilation1, benchmark=False,
TF32 off다. 각 실행에 새 Pod를 사용했고 허용 오차는 rtol1e-4/atol1e-6으로 고정했다.

| 실행 | GPU step | 비교 텐서 | 결과 |
|---|---:|---:|---|
| Conv→ReLU | 10 | 70 | PASS |
| Conv→ReLU→MaxPool | 10 | 70 | PASS |
| 두 Conv 블록+Linear, synthetic labels | 20 | 300 | PASS |
| 동일 CNN, 새 Pod 반복 | 20 | 300 | PASS |
| MNIST80개 샘플, 5개 minibatch | 20 | 300 | PASS |
| CNN 합계 | 80 | 1,040 | PASS |
| 기본 cuBLASLt MLP | 5 | 22 | PASS |
| 기본 cuDNN LSTM | 5 | 36 | PASS |
| basic matmul | — | — | PASS |
| 공개 workload SGEMM·30초 idle, 2회 | — | 전체 2×2 결과 | PASS |

CNN의 출력·loss·입력 gradient·모든 파라미터 gradient·갱신 파라미터를 저장했다.
`cnn/tensor-audit.json`은 autograd backward를 쓰지 않는 Conv/ReLU/MaxPool/Linear/loss
역전파 수식과 수동 SGD로 CPU/GPU 결과를 검산한 기록이다. 1,040개 GPU 텐서가
모두 일치했고 최대 절대 오차는 `4.76837158203125e-7`이다.
독립 감사에만 로컬 `2.11.0+flyt.cu128` CPU 환경을 사용했다.
공개 GPU 실행의 PyTorch image와 혼용하지 않는다.

첫 GPU 프로세스 관측은 컨테이너 PID namespace에서 호스트 NVML 프로세스가 보이지 않아
일치 기록을 얻지 못했다. GPU 학습 실패가 아니다. host PID namespace에서 공개 workload의
idle probe를 다시 관측해 할당 GPU UUID·host PID·NSpid·Worker session PID를 연결했다.
실패한 관측 로그와 성공한 `gpu-observation.json`을 함께 보존했다.
이 관측은 SGEMM/idle probe의 물리 GPU 실행 증거이며 CNN 실행 중의 성능 표본은 아니다.

## 유지한 구성과 한계

기존 Helm namespace·TLS·mode·할당량은 유지하고 image digest와 Plugin Guest hash만
갱신했다. 원래 Profile/Request와 PVC의 UID/spec는 보존했다. VM은 동일 UID를 유지하고
새 연결의 binding·hook image만 바뀌었다. 보호 중인 control-plane VMI의 UID/spec와
기존 회수 미완료 Channel의 UID/spec도 유지했다. `preservation.json`을 확인한다.
finalizer 강제 삭제나 SHM 수동 삭제는 하지 않았다. Kubernetes/KubeVirt/GPU Operator 및
외부 HAMi device plugin/DRA driver는 업그레이드하지 않았다.

기본 cuDNN graph, BatchNorm, AMP, ResNet/YOLO, 전체 MNIST의 정확도·수렴,
실제 규모 처리량은 검증하지 않았다. CNN에는 `TORCH_CUDNN_V8_API_DISABLED=1`이 필요하다.
새 클러스터 전체 GPU 설치 검증은 NOT_RUN이다. 기존 제한을 새 버전의 포괄적 지원으로
확대하지 않는다.

## 재검증

```sh
python3 deploy/releases/evidence/v0.5.10/validate.py
# CPU PyTorch 환경에서 원시 CNN 텐서 재검산
python3 experiments/cnn-model/audit_tensors.py \
  --results deploy/releases/evidence/v0.5.10/cnn --run-prefix published-
```

`artifacts.json`은 보존 파일 hash 목록이다. 공개 소스·검증 도구는 `source/`에,
사설 연결 정보와 전체 Helm values 백업은 `.local/`에 둔다. 과거 릴리스 JSON과
후보 실험 결과의 bytes/hash는 변경하지 않았다.
