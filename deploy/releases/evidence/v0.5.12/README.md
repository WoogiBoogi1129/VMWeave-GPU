# v0.5.12 / Device Plugin 0.1.4 배포 검증

2026-11-18. 등록된 typed default-stream 커널의 선택적 제출 배치를 공개하고,
중앙 Operator와 기존 유휴 GPU VM의 Guest·Worker·helper·hook·Device Plugin을 갱신했다.
최종 결과는 [validation.json](validation.json), 배치 정답 검증은
[batch/validation.json](batch/validation.json), 환경 보존은
[preservation.json](preservation.json)을 따른다.

## 적용 범위

- 빌드 소스: `2cd0fe428f2ee2b99fa43777b2967854904966ac`.
- Runtime/Operator chart: **0.5.12**, Device Plugin chart: **0.1.4**.
- 중앙 release: `vmweave-system/vmweave` 하나. 이전에 통합된 namespace·TLS·mode를 보존했다.
- GPU VM: `vmweave-test-b/dp-dev-20261105`. 기존 GPU2·25% compute·1024MiB·1슬롯을 유지했다.
- 새 immutable Profile/Request: `dp-dev-20261105-v0512`. 이전 Profile/Request는 롤백용으로 보존했다.
- Broker에는 BULK_COPY·BROKER_REUSE·BROKER_GATHER·BROKER_OWNER를 활성화했다.
  애플리케이션의 bulk/direct와 kernel batch는 환경 변수를 명시해야 한다.
- **커널 배치는 기본 비활성화**다. 전체 Pod 또는 기존 모델에 일괄 활성화하지 않았다.

공개 패키지 checksum, source revision, Runtime Guest와 Plugin Guest의 라이브러리 해시를 비교했다.
[패키지 일치](guest-package-equivalence.json), [게시 이미지](published-images.json),
[실제 Controller/Webhook imageID](deployments-after.json), [Worker](worker-pod-after.json).
이번 공개 Guest 해시는 앞선 GPU1 후보 실험과 동일하지만 이번 배포 검증은 성능 측정이 아니다.
Worker 실행 파일은 공개 빌드에서 재생성되어 후보의 바이너리 해시와 다르다.
[바이너리 비교](candidate-binary-equivalence.json)와 [실제 Worker 해시](worker-binaries.txt)를 보존했으며,
새 공개 Worker를 대상으로 아래 GPU 회귀를 다시 수행했다.

## 검증

- 공개 Guest/Worker의 batch off/on: 1,003개 이상 순서 의존 커널, 호출자 인자 변경,
  D2H·stream sync·직접 H2D·module unload 순서 및 정답 PASS.
- 배치 launch 오류의 지연 전달·실패 세션 종료 및 새 정상 세션 회복 PASS.
- 공식 PyTorch 이미지에서 legacy CNN·MLP·LSTM·기본 CUDA와 공개 SGEMM workload PASS.
  CNN의 CPU 기준과 독립 수동 역전파/SGD 검산은 [tensor audit](cnn/tensor-audit.json)을 따른다.
- GPU PID를 갱신된 Worker Pod cgroup 및 CUDA child PID와 대응했다.
  [GPU 경로 관측](gpu-observation.json).
- 최종 VM/VMI Running, Channel Ready, Broker 유휴, Plugin GPU 1슬롯 할당 가능 상태를 확인했다.
- 임시 관리 Pod·검증 namespace·Guest 임시 설치 파일을 제거했다. 기존 VLLM 등 다른 실행 Pod는
  UID·Ready·재시작 횟수를 비교했으며 공용 Helm release와 HAMi 설정도 비교했다.

CPU CI의 첫 `ubuntu-latest` 실행은 runtime regression 단계에서 실패했다.
동일 CPU 검사는 로컬에서 통과했으며, 다른 이미지 빌드와 동일한 Ubuntu 24.04로 CI를 고정하고
오류 진단 출력을 추가한 후 전체 CPU CI가 통과했다. 런타임 소스는 바뀌지 않았다.
최초 실패와 재검증을 [Actions 기록](actions-final-build.json)에 함께 보존했다.
이를 CUDA 런타임 결함의 수정 또는 원인 규명의 증거로 해석하지 않는다.

## 제한과 롤백

이번 확인은 배포·정답·기존 지원 모델 회귀 검증이다. GPU1에서 수행한 이전 성능 실험,
Flyt/Lupine과의 직접 비교, 전체 CUDA 호환성 또는 성능 비열등성 증명으로 대체하지 않는다.
배치에는 최대 128 launches/packet, 지연 오류, 단일 in-flight packet과 200µs 타이머 목표의 제한이 있다.
다중 stream과 일반 PyTorch 모델의 배치 효과는 검증하지 않았다.
CNN의 기존 legacy FP32 NCHW·`TORCH_CUDNN_V8_API_DISABLED=1` 제한도 유지된다.

기존 Draining Channel 3개를 강제 회수하지 않았다. Kubernetes·KubeVirt·HAMi·DRA·GPU Operator는
업그레이드하지 않았다. HAMi 관련 릴리스 이미지를 게시한 것과 운영 인프라 교체는 별개다.

롤백용 이전 Profile/Request·이미지와 Guest의 `/home/ubuntu/v0512-guest-backup.tar.gz`를 보존했다.
활성 GPU 작업이 없는지 확인하고 VM 정상 정지·Channel 회수 후 이전 Guest·Worker·Plugin 및
환경 설정을 함께 복원해야 한다. 실행 중 Broker를 재시작해 기존 SHM ring에 다시 연결하지 않는다.

```sh
python3 deploy/releases/evidence/v0.5.12/validate.py
```
