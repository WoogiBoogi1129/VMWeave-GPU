# GPU 환경 준비

실제 검증은 특정 단일 노드 환경에서 수행했습니다. 설치 성공, VM 매핑 성공,
CUDA 실행 성공과 성능 검증을 각각 확인해야 합니다.

## 요구 조건

- CUDA 12.8 계열과 현재 런타임이 사용하는 cuDNN 9 개발/실행 라이브러리.
- GPU 자원을 등록하고 Worker에 정책을 적용하는 HAMi.
- Sidecar hook 및 ivshmem을 지원하는 KubeVirt/QEMU 구성.
- VM과 Worker가 사용하는 동일 노드의 로컬 filesystem PVC.
- 일치하는 Guest/Worker ABI, 이미지 digest, layout 및 Guest 장치 정보.

[검증 당시 설치 보고서](../../legacy/docs/installation/INSTALLATION_REPORT_2026-09-22.md)의
버전 조합은 그 환경의 기록입니다. 모든 Kubernetes/KubeVirt 버전 조합의 지원 선언은 아닙니다.

## 준비 순서

1. [CPU review](cpu-control-plane.md)에서 제어기와 admission을 확인합니다.
2. [런타임 빌드](../development/index.md) 후 Worker·Guest·hook 산출물의 digest/해시를 기록합니다.
3. [중앙 설치](install.md)의 active 설정에 사용자 namespace를 등록합니다.
4. 승인 Profile, 정지 VM, Request, Channel과 로컬 PVC를 준비합니다.
5. [첫 VM 실행](first-vm.md)에 따라 새 API의 매핑과 GPU smoke를 확인합니다. 과거 실험 재현 문서는 구API 기록입니다.
6. [학습 재현 절차](../../experiments/evidence/REPRODUCE_PYTORCH.md)는 고정 PyTorch 빌드·모델의 별도 검증으로 수행합니다.

설치 당시 보조 파일은 [scripts/installation](../../scripts/installation/)에 보존했습니다.
호스트 서비스 복구 스크립트에는 당시 환경 경로가 있으므로 일반 설치기로 취급하지 않습니다.

## 결과 보존

새 실험 디렉터리에 실행 명령·환경·UID·digest·출력·회수 증거를 저장합니다.
SSH 키와 TLS 키를 포함할 수 있는 `.local/` 전체를 공개하지 않습니다.
[증거 보존 정책](../evaluation/artifacts.md)을 따르세요.
