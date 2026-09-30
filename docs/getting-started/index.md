# 시작하기

VMWeave는 `vmweave-system`에 중앙 Go Controller와 Webhook을 설치합니다.
사용자는 각자의 namespace에 VM, PVC와 `vmweave.io/v1alpha1` 리소스를 생성합니다.
KubeVirt의 virt-launcher와 VMWeave Worker·prepare·reclaim Pod도 VM의 namespace에 생성됩니다.

1. 관리자: [사전 조건](prerequisites.md)과 [중앙 설치](install.md).
2. 관리자: [사용자 namespace 등록](namespaces.md).
3. 사용자: [첫 VM 실행과 회수](first-vm.md).
4. 운영자: [업그레이드·제거](../guides/upgrade-uninstall.md).
5. 기존 사용자: [flyt.dev 데이터 이전](../guides/migrate-to-vmweave-api.md).

GPU 없이 제어 영역을 확인할 때는 같은 설치 경로의 [review 모드](cpu-control-plane.md)를 사용합니다.
GPU 의존성은 [GPU 준비](gpu.md), 이번 전환의 검증 범위는
[Operator 검증 기록](../development/operator-validation.md)에 정리합니다.

`charts/flyt-control-plane`, `scripts/install-control-plane.py`, 이전 실험 문서의 설치 명령은
구API 회수·재현용으로 보존합니다. 새 설치에는 위 중앙 설치 경로를 사용합니다.
