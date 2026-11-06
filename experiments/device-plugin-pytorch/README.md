# 공식 PyTorch 이미지와 VMWeave Device Plugin 기능 검증

공식 `pytorch/pytorch` 이미지의 PyTorch·CUDA 파일을 교체하지 않고, VM 내부 Kubernetes에서
Device Plugin을 통해 GPU 연산과 작은 FP32 학습을 실행할 수 있는지 검증한다.
2026-11-06 검증에서 GPU 기초 연산과 5-step 학습이 통과했다. 이 이미지의 기본 `Linear` 경로는
exit 139로 실패하며, `DISABLE_ADDMM_CUDA_LT=1`이 필요했다. 이 설정을 사용하면 SGD 기본 옵션의
학습도 통과한다. 사전 정의 `compat` 프로파일에서 정상/강제 종료 후 재사용까지 확인했다.
SGEMM 처리량·성능 비교·nested HAMi는 이 실험에 포함하지 않는다.

- [사전 계획과 판정 기준](plans/functional.md)
- [2026-11-06 실제 검증 결과](results/20261106-official/REPORT.md)
- [기능 검증 workload](workloads/verify.py)
- [Pod 실행·수집 도구](runner/run.py)

## 실행 준비

먼저 [Device Plugin 설치 안내](../../docs/guides/kubernetes-device-plugin.md)에 따라 Guest Broker와
Device Plugin을 설치한다. VM의 실제 `vmweave` 그룹 GID, 내부 Kubernetes context와 node 이름을
확인하고, 사용하지 않는 전용 namespace/runID를 선택한다. 기존 실행 결과 디렉터리는 재사용하지 않는다.
GPU 이미지와 Guest adapter digest는 `runner/run.py`에서 고정한다.

SSH 연결 정보는 Git에 넣지 않는 별도 JSON에 저장한다. 다음은 형식 예시이며 실제 접속 정보가 아니다.

```json
{
  "sshArgv": ["ssh", "-i", "/private/path/key", "-oBatchMode=yes", "ubuntu@VM_ADDRESS"],
  "context": "kubernetes-admin@YOUR_CLUSTER",
  "namespace": "dp-torch-new-run",
  "runID": "official-pytorch-new-run",
  "node": "YOUR_VM_NODE",
  "brokerGID": 998
}
```

namespace는 Kubernetes 이름 규칙에 맞는 소문자로 정한다. SSH 접속 계정의 kubectl이 내부 클러스터의
시험 namespace 생성·Pod 실행·로그 수집 권한을 가져야 한다. `prepare`는 이미 있는 namespace에
덮어쓰지 않는다. 이후 명령은 namespace의 실행 소유 label을 확인한다.

```bash
python3 experiments/device-plugin-pytorch/runner/run.py \
  --connection /private/path/connection.json --results /private/path/new-results prepare
python3 experiments/device-plugin-pytorch/runner/run.py \
  --connection /private/path/connection.json --results /private/path/new-results \
  run --name torch-cpu --mode cpu
python3 experiments/device-plugin-pytorch/runner/run.py \
  --connection /private/path/connection.json --results /private/path/new-results \
  run --name torch-gpu --mode gpu --profile compat
```

CPU baseline의 성공을 확인한 후 GPU Pod를 실행한다. 위 GPU 명령은 성공한 `compat` 조건이다.
기본 경로의 실패 재현은 별도 이름으로 `--profile default`를 사용한다.
SGD 기본 옵션을 유지하려면 [Lt 우회만 적용한 선언](manifests/gpu-pod-no-lt-only.yaml)을 참고한다.
이 선언의 namespace·node·GID를 실제 값으로 바꾸고, 같은 namespace에 `verify-code` ConfigMap을 준비한다.

`run`은 Pod 실패 시 종료 코드 1을 반환한다.
`render --name NAME --mode gpu`는 API 변경 없이 JSON manifest를 출력한다(JSON은 Kubernetes YAML 입력과 호환된다).
`collect --name NAME`은 기존 Pod의 API JSON·로그·describe를 수집한다.
`--no-wait`는 생성까지만 수행하므로 이후 `collect`와 실제 Pod 결과 확인이 필요하다.

## 기능과 중단 경계

GPU Pod는 `vmweave.io/gpu: 1`을 요청한다. initContainer는 Guest library만 공유 emptyDir에 복사하고
SHA256을 확인한다. workload는 non-root로 공식 이미지를 실행하며, Plugin이 broker socket과 접속
환경변수를 주입한다. 선언 manifest에 broker hostPath를 직접 추가하지 않는다.

`verify.py`는 공식 PyTorch 파일 hash와 버전, CPU 참조값, CUDA 초기화, H2D/D2H, 덧셈·행렬곱,
5-step MLP 학습 순서로 판정한다. step 1·5의 전체 출력·loss·gradient·weight를 고정 허용 오차로 비교한다.
`mode=hold`는 CUDA 기초 연산 뒤 지정 시간 동안 세션을 유지하는 회수 검증용이다.
`--hold-seconds`와 `--killable`은 전용 시험 Pod의 순차 예약·SIGKILL 확인에만 사용한다.

기본 프로파일이 실패하면 이후 단계의 성공으로 간주하지 않는다. `compat`는 사전 명시한
cuBLASLt/SGD 옵션만 변경하는 별도 조건이며 필요성이 확인될 때만 실행한다.
공식 wheel 교체나 CPU 자동 fallback은 허용하지 않는다. 실행 도구는 VM 정지·Pod 삭제를 자동 수행하지
않으므로 증거 수집 후 시험 VM의 정상 종료와 외부 Channel 회수를 별도로 확인해야 한다.

## 보존된 증거

결과에는 공식 이미지 식별자·파일 hash, 9개 Pod의 선언/API 상태/로그/describe, 전체 tensor snapshot,
실제 GPU PID 대응, 종료 기록과 11개 터미널 PNG를 포함한다. 기본 경로 실패 2건과 의도한 SIGKILL의
exit 137도 그대로 남겼다. 결과의 SHA256SUMS는 해당 결과 디렉터리에서 검증한다.

`runner/capture.cjs`는 Playwright·Chromium·tmux·ttyd와 별도 SSH 설정을 사용하는 실제 화면 촬영 도구다.
로그를 이미지로 다시 그리지 않는다. 연결 키·접속 설정은 저장소에 포함하지 않는다.
