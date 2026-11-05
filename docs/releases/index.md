# 현재 릴리스와 배포 기록

현재 공개 릴리스는 **v0.5.8**이며 Operator/chart 기준이다. 2026-11-04의 공개·배포 결과는
[릴리스 기록](../../deploy/releases/v0.5.8.json)과 [검증 원본](../../deploy/releases/evidence/v0.5.8/README.md)에 있다.
기계 판독 진입점은 [current.json](../../deploy/releases/current.json)이다.

| 목적 | 확인할 자료 |
|---|---|
| v0.5.8 변경·필수 CRD/RBAC·롤백 제한 | [회수 기록 복구 릴리스 안내](../getting-started/release-v0.5.8.md) |
| 현행 설치 | [관리자 설치](../getting-started/install.md) → [namespace 등록](../getting-started/namespaces.md) → [첫 VM](../getting-started/first-vm.md) |
| 기존 환경 변경 | [업그레이드·제거](../guides/upgrade-uninstall.md)와 대상 릴리스 안내 |
| 이미지 digest·chart version | 위 릴리스 JSON의 `images`, `chart` |
| 새 클러스터 배포의 전제 | [배포 기준과 v0.5.2 재현 절차](../getting-started/portable-deployment.md) |

공개 이미지와 실제 유지된 실행 이미지의 버전은 다를 수 있다. v0.5.8 배포는 Controller/Webhook,
추가 CRD schema와 chart RBAC를 갱신하고 활성 Guest·Worker 등의 이미지 참조를 유지했다.
`images`는 해당 릴리스의 배포물, `activeChannelImagesRetained`와 `externalComponentsNotUpgraded`는
그 배포에서 유지한 구성이다. 모든 이미지 태그를 일괄 v0.5.8로 바꾸는 업그레이드 절차가 아니다.

릴리스의 API/filesystem canary는 실제 GPU detach나 새 VM 부팅 시험을 대신하지 않는다.
새 별도 클러스터의 전체 GPU 설치 검증은 여전히 NOT_RUN이다.

이전 기록: [v0.5.7](../getting-started/release-v0.5.7.md),
[v0.5.6](../getting-started/release-v0.5.6.md), [v0.5.5](v0.5.5.md),
[v0.5.4](../getting-started/release-v0.5.4.md), [v0.5.3](v0.5.3-candidate.md),
[v0.5.2](../getting-started/release-v0.5.2.md).
구 Flyt PoC의 `v1.0.0`은 현재 VMWeave 릴리스가 아니다.

릴리스 시 `current.json`, 본문, chart, `versions.lock.yaml`을 함께 검토한다.
개발 중 chart 버전은 공개 릴리스와 달라도 되지만 chart와 lock은 일치해야 한다.
과거 릴리스 JSON·digest·증거는 수정하지 않는다.
