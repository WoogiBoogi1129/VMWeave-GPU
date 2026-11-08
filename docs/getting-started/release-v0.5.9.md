# VMWeave v0.5.9: 기본 cuDNN LSTM·cuBLASLt 경로

공식 PyTorch의 FP32 LSTM 학습을 cuDNN 비활성화나
`DISABLE_ADDMM_CUDA_LT=1` 설정 없이 실행하도록 Guest와 Worker의 라이브러리 중계를 추가했다.
RNN descriptor·가중치/임시 공간 조회·forward/backward와 cuBLASLt FP32 행렬곱을 포함한다.
PyTorch가 cuBLAS handle을 Lt 연산에 사용하는 경로와 cuDNN의 선택적 출력 인자도 처리한다.

## 배포 단위

- Operator Helm chart: **0.5.9**. 기존 관리 namespace, TLS, mode와 할당량을 유지한다.
- Runtime: **v0.5.9 Guest와 Worker를 함께 배포**한다. 구 Worker는 새 RPC를 지원하지 않는다.
- 선택적 내부 Kubernetes Device Plugin: **0.1.1**. 새 Guest package와 workload 이미지를 포함한다.
  Plugin의 `librarySHA256`은 설치한 Guest 라이브러리의 실제 hash와 일치해야 한다.
- CRD·RBAC 변경은 없다. v0.5.8의 회수 journal 및 롤백 제한은 그대로 적용한다.

[릴리스 JSON](../../deploy/releases/v0.5.9.json)의 image digest와
[Device Plugin 기록](../../deploy/releases/device-plugin-v0.1.1.json)을 사용한다.
Helm만 갱신하면 기존 VM 디스크의 Guest 라이브러리나 GPUProfile/Channel의 Worker 이미지가
자동으로 교체되는 것은 아니다.

## 기존 VM 업데이트 순서

1. 기존 Helm values, VM/Profile/Channel 정의와 Guest package 식별자를 보관하고 GPU 작업을 종료한다.
2. 새 Guest package의 checksum을 검증한다. 정지된 디스크에 설치하거나, 활성 client가 없는 VM에서
   Broker를 중지하고 설치한 뒤 즉시 VM을 정상 종료한다. 같은 SHM 연결에서 Broker를 다시 시작하지 않는다.
3. VMI가 사라지고 Channel이 `Stopped`가 된 것을 확인한다. GPUProfile의 Worker image와
   Request의 profileRef, Channel의 연결 spec은 변경 불가이므로 새 버전의 Profile/Request를 만든다.
   기존 Channel을 정상 삭제한 뒤 같은 VM·PVC를 참조하는 새 Channel을 만들고 새 Worker/helper/hook
   digest를 지정한다. VM과 root/SHM PVC는 유지하며 finalizer를 강제로 제거하지 않는다.
   VM template에 이전 Channel UID의 binding annotation이 남으면, VM 정지·VMI 부재·이전 Channel의
   정상 회수·삭제를 확인한 뒤 그 이전 binding의 annotation만 UID/resourceVersion 조건으로 제거한다.
   새 Controller가 새 연결의 annotation과 cloud-init layout을 생성하도록 한다.
4. VM을 시작해 새 allocation/generation과 Broker Ready를 확인한다.
5. 내부 Kubernetes를 사용하면 새 Plugin chart/image와 `librarySHA256`으로 Helm upgrade한다.
   Pod initContainer가 사용하는 Guest image도 같은 검증 릴리스로 갱신한다.
6. GPU 자원 등록, 기본 CUDA 연산, LSTM 학습과 세션 회수를 확인한다.

롤백도 GPU 작업 종료와 새 binding 생성을 거쳐 호환되는 Guest/Worker 쌍으로 수행한다.
이전 버전으로 돌아가면 이번 기본 LSTM 경로는 사용할 수 없다.

## 검증 범위

[후보 실험](../../experiments/rnn-default/results/20261108/REPORT.md)은 MNIST 1,024개를 사용한
단층·단방향 FP32 LSTM의 128-step 학습, CPU 검산, 새 Pod의 체크포인트 재개와 MLP 회귀를 포함한다.
[공개 배포물 검증](../../deploy/releases/evidence/v0.5.9/README.md)은 실제 게시된 이미지와 chart를
노드에 설치해 다시 실행한 결과다. 후보와 공개 바이너리의 hash를 혼용하지 않는다.

RNNData FP32·unpacked, Lt FP32 host scalar·열 우선 layout의 제한된 구현이다.
Lt algorithm/heuristic 전송은 CUDA12.8 x86-64 ABI에 한정한다.
CNN·AMP·분산 학습·모든 RNN 설정을 검증한 것이 아니며, 이번 짧은 학습의 낮은 정확도로
유의미한 수렴이나 범용 workload 호환성을 주장하지 않는다. 처리량 비교도 별도 과제다.

현재 노드의 적용 대상과 유지한 구성은 릴리스 JSON에 구분해 기록한다.
과거 회수 미완료 Channel의 finalizer나 증거를 강제로 제거하지 않는다.
