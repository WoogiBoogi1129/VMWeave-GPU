# v0.5.11 / Device Plugin 0.1.3 공개·배포 검증

2026-11-13 (Asia/Seoul). 고정 GPU 슬롯과 미배치 Worker 회수 수정을 공개하고,
기존 두 Operator 및 GPU VM의 Guest/Worker/Plugin을 게시 산출물로 갱신했다.
최종 판정은 [validation.json](validation.json)과 재검증 가능한 [validate.py](validate.py)를 따른다.

## 버전과 소스

- Build source: `f6c6ab7acc28fc91d409110a7539a0d22b759ce2`.
- Runtime/Operator chart: **v0.5.11 / 0.5.11**.
- Guest Kubernetes Device Plugin chart: **0.1.3**.
- [Runtime digest·배포 기록](../../v0.5.11.json), [Plugin 이미지·chart·다운로드 hash](../../device-plugin-v0.1.3.json).
- [공개 이미지](published-images.json), [Helm release 상태](helm-releases.json),
  [Controller/Webhook의 실제 imageID와 Ready](deployments-after.json).
- Guest library SHA256: `08ccac5fb763451e448a68700f6156a6e0eba62950614913fb07c62ba966cfa0`.

공개 Runtime Guest와 Plugin Guest의 source revision·library hash가 일치한다.
[Guest package 비교](guest-package-equivalence.json).
이전 v0.5.10과 [Guest C 바이너리](guest-binary-comparison.json),
[두 Worker 실행 파일](worker-binary-comparison.json)의 hash도 동일하다.
새 제어 Python 파일은 [공개 패키지 추출본](source/guest_bootstrap.py)의 hash를
[소스와 비교](published-control-equivalence.json)했다. OCI revision label은 소스 추적 자료이며
독립적인 암호학적 provenance 증명으로 해석하지 않는다.

## 적용 내용

`nested`와 `vmweave`의 Controller/Webhook 4개를 새 digest로 교체했다.
기존 management namespaces·TLS·mode·GPU 예산·외부 인프라 버전은 보존했다.
GPU VM `vmweave-test-b/dp-dev-20261105`는 유휴 상태 확인 후 Guest package 설치,
정상 정지와 backing 회수, 새 immutable Profile/Request/Channel 생성, 재부팅,
Plugin Helm upgrade 순서로 갱신했다. 기존 1슬롯 설정은 유지했다.
이전 Profile/Request는 롤백용으로 보존했다.

실험용 `fixed` Operator의 namespace·RBAC·Webhook 잔여 리소스가 없음을 확인했고,
사용했던 두 후보 Operator 이미지도 rootless 및 host CRI store에서 제거했다.
[리소스 확인](experimental-resource-cleanup.json), [이미지 제거](experimental-operator-images-cleanup.json).
배포용 임시 관리 Pod와 GPU 검증 namespace도 제거했다.
[환경 보존 및 정리 결과](preservation.json).

## GPU 검증

게시된 Plugin Guest/Worker를 사용하는 공식 PyTorch image에서 다음을 다시 검증했다.

| 항목 | 결과 |
|---|---|
| legacy CNN 조합·반복·MNIST 일부 | GPU 80 step, 1,040개 텐서, 독립 수동 역전파·SGD 검산 PASS |
| 기본 cuBLASLt MLP | 22개 텐서 PASS |
| 기본 cuDNN LSTM | 36개 텐서 PASS |
| 기본 CUDA matmul | PASS |
| 공개 workload image의 SGEMM·idle 30초 | PASS, [로그](published-idle/stdout.txt) |
| 실제 GPU 경로 | Worker Pod UID의 cgroup과 NSpid를 GPU PID에 대응. [관측](gpu-observation.json) |
| 최종 상태 | VM/VMI Running, Channel Ready, Broker Ready·비활성 client, 시험 namespace 제거 |

[전체 사례](validation.json), [독립 CNN 감사](cnn/tensor-audit.json),
[최종 Broker](broker-final.json), [최종 Channel](sharedmemorychannel-after.json).
CPU/배포 계약 검사는 [Operator](operator-check.log), [배포](deployment-tests.log),
[Plugin packaging](plugin-packaging.log) 로그와 GitHub Actions 실행 기록으로 구분한다.

2슬롯 동시 GPU 실행·슬롯 재사용·Broker 부분 장애의 실제 증거는
[발행 전 후보 실험](../../../../experiments/fixed-slots/results/20261113/REPORT.md)이다.
게시한 Guest 제어 파일과 그 후보 소스의 hash 일치를 확인했다.
**이번 공개 패키지의 최종 배포 회귀는 기존 1슬롯 VM에서 수행했다.**
후보 실험의 2슬롯 결과를 새 공개 이미지로 다시 실행한 결과처럼 표시하지 않는다.

## 유지되는 제한

- 고정 1~2슬롯은 VM GPU quota를 공유한다. Pod별 VRAM·compute 보장 및 공정성은 제공하지 않는다.
- 강제 Pod 삭제 직후 새 접속은 `busy(46)`로 거부될 수 있다. 실제 CUDA child 회수 확인 또는
  새 실행 재시도가 필요하다.
- Broker 장애 시 해당 슬롯을 자동 재시작하지 않는다. Host CUDA child와 VRAM은
  VM 전체 정지·binding 회수 전까지 남을 수 있다.
- CNN은 `TORCH_CUDNN_V8_API_DISABLED=1`, FP32 contiguous NCHW, groups=1,
  dilation=1, benchmark=False의 제한된 경로다. 전체 모델 호환성·수렴·처리량 검증이 아니다.
- 기존 Draining Channel 3개는 증거 없는 finalizer/SHM 강제 정리를 하지 않고 보존했다.
- Kubernetes/KubeVirt/HAMi/GPU Operator/DRA driver 자체는 업그레이드하지 않았다.
  HAMi 관련 릴리스 이미지를 게시한 것과 기존 인프라 교체는 구분한다.
- 새 별도 클러스터 전체 설치 검증은 NOT_RUN이다.

```sh
python3 deploy/releases/evidence/v0.5.11/validate.py
```

`artifacts.json`은 이 디렉터리의 검증 자료 hash를 기록한다.
개인 키·kubeconfig·다운로드 image archive는 포함하지 않는다.
