# 최소 Conv2d forward 중계 후보

2026-11-13: v0.5.9 기반의 legacy cuDNN Conv2d forward 중계를 구현하고
**동일 시험 VM에서 GPU forward 198건 및 기존 MLP·LSTM 학습 회귀를 검증했다.**
[VM 검증 결과](results/20261113-vm/REPORT.md)를 먼저 확인한다.
후속 backward·최소 학습 구현과 검증은 [cnn-training](../cnn-training/README.md)에 기록한다.
[최초 호스트 검증·환경 차단 기록](results/20261113/REPORT.md)은 당시 상태로 보존한다.
CNN 학습 전체 지원 완료를 의미하지 않으며 backward, BatchNorm, 기본 cuDNN graph 경로는
범위 밖이다. 기본 graph 경로는 후보에서도 첫 forward에서 SIGSEGV가 재현됐다.

## 범위와 판정

- FP32 contiguous NCHW, 2D cross-correlation, groups=1, dilation=1.
- 입력 `[2,3,8,8]`, 출력 채널 4, kernel 3. bias on/off, stride 1/2, padding 0/1.
- deterministic on/off를 구분해 기본 알고리즘 및 heuristic 경로를 검사한다.
  `benchmark=False`, TF32 off, SGD/backward 실행 없음.
- 기본 스트림과 명시적 스트림에서 각각 3회 forward. CPU 참조와 `rtol=1e-4,
  atol=1e-6`으로 비교한다. 16개 설정 × 2개 스트림 × 3회 = 96개 GPU 결과가 대상이다.
- `--backend legacy`는 import 전에 `TORCH_CUDNN_V8_API_DISABLED=1`을 설정한다.
  `--backend default`는 해당 변수를 제거한다. 실패 시 자동 재시도·fallback하지 않는다.
- `--case stream`은 `RTLD_DEFAULT`의 Guest wrapper를 호출한다.
  Nov 7의 의도적인 native `cudnnSetStream` 충돌 재현 코드를 재사용하지 않는다.
- 성공한 GPU 비교뿐 아니라 Worker의 `VMWEAVE_LIBRARY_TRACE=1` 기록에서
  `cudnnConvolutionForward` (`0x3333`, decimal 13107) 실행을 확인해야 한다.
  마지막 CPU-only PASS나 mocked execution 테스트는 이 판정을 대신하지 않는다.

## 검증 순서

1. 시험 VM `vmweave-test-b/dp-dev-20261105`의 상태·이미지·UID를 캡처한다.
   이번에는 재부팅 후 `Draining/AwaitingDetachEvidence`가 남아 있었다.
   `recover_detach.py`로 재부팅·sandbox 소멸·mapping/FD/프로세스/CRI 부재를 검증하고
   검증 근거를 Guest detach 상태에 기록한 뒤 컨트롤러가 정상 회수했다.
   finalizer 직접 삭제나 detach 증거 없이 상태를 바꾸는 작업은 하지 않았다.
2. 공개 v0.5.9 Guest/Worker + Plugin v0.1.1에서 `stream`, `minimal`을 재진단한다.
   default와 legacy는 서로 다른 Pod로 실행하고 실패 로그도 보존한다.
3. 동일 소스에서 빌드한 후보 Guest/Worker를 시험 VM에 함께 적용한다.
   기존 Profile/Request/Channel의 immutable 계약을 따라 별도 후보를 구성한다.
   runner는 Worker 배포나 VM 시작/종료를 수행하지 않는다.
4. `stream` → `minimal` → `matrix`를 실행하고 새 Pod에서도 재현한다.
   CPU 비교, 실제 Worker 호출, 프로세스 종료 후 회수·재사용을 함께 검사한다.
5. 기존 `experiments/rnn-default/runner/run.py`로 기본 Lt MLP·LSTM 학습을 회귀 검증한다.
   실패 시 CNN backward로 확장하지 않는다. 원래 런타임과 시작 상태로 복구한다.

## 실행 도구

연결 JSON은 기존 실험의 `sshArgv`, `context`, `node`, `brokerGID` 형식을 사용하며
`namespace`, `runID`는 `cnn-forward-` 접두사를 사용한다. 비밀 정보는 `.local/`에만 둔다.

`render`는 로컬 manifest만 생성한다. `run`은 먼저 호스트의 Ready Channel 및
기대한 Worker의 실제 Ready/imageID를 검사하고, 다른 GPU Pod가 없을 때만 실행한다.
기본 template은 공개 v0.5.9 검증의 pinned official PyTorch 및 Guest 이미지다.
후보는 `--guest-library`와 `--worker-image`를 반드시 함께 지정한다.

```sh
python3 experiments/cnn-forward/runner/run.py render \
  --connection .local/cnn-forward-20261113/connection.json \
  --results .local/cnn-forward-20261113/review \
  --name baseline-default --backend default --case minimal --loader-trace

# Ready Channel 및 paired candidate 배포 후 실행
python3 experiments/cnn-forward/runner/run.py run \
  --connection .local/cnn-forward-20261113/connection.json \
  --results experiments/cnn-forward/results/<new-run> \
  --name candidate-matrix --backend legacy --case matrix \
  --guest-library .local/cnn-forward-20261113/build/libvmweave_guest.so \
  --worker-image <candidate-worker-image@sha256:digest>
```

Pod는 240초, probe subprocess는 120초 제한이다. signal/timeout, loader trace,
CPU/GPU 텐서, Pod 이미지·manifest 및 소스 hash를 수집한다. `collect`로 재수집할 수 있다.
실패·성공 Pod의 증거를 수집한 후 해당 실험 namespace만 정리한다.

VM 증거 검증: `python3 experiments/cnn-forward/validate_vm.py`.
원시 텐서 재검산: `python3 experiments/cnn-forward/audit_tensors.py` (CPU PyTorch 필요).
최초 호스트 단계 증거 검증: `python3 experiments/cnn-forward/validate.py`.
실제 VM 검증은 공식 `2.11.0+cu128` 이미지다. 최초 CPU self-check와 후속 독립 텐서
재검산만 로컬 `2.11.0+flyt.cu128`의 CPU 기능을 사용했다.

후속 [v0.5.10·Plugin0.1.2 공개 배포물 검증](../../deploy/releases/evidence/v0.5.10/README.md)에서
게시된 Guest/Worker와 Helm을 적용해 확인했다. 이 디렉터리의 후보 결과·해시는 당시 기록으로 보존한다.
