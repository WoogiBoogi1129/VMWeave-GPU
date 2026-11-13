# 현재 릴리스와 배포 기록

현재 공개 릴리스는 **v0.5.10**이다. 2026-11-13의 공개·배포 결과는
[릴리스 기록](../../deploy/releases/v0.5.10.json)과 [검증 원본](../../deploy/releases/evidence/v0.5.10/README.md)에 있다.
기계 판독 진입점은 [current.json](../../deploy/releases/current.json)이다.

| 목적 | 확인할 자료 |
|---|---|
| v0.5.10 legacy CNN·Guest/Worker 동시 업데이트 | [릴리스 안내](../getting-started/release-v0.5.10.md) |
| 이전 v0.5.9 기본 LSTM 경로 | [LSTM 릴리스 안내](../getting-started/release-v0.5.9.md) |
| 이전 v0.5.8 회수 journal·롤백 제한 | [회수 기록 복구 안내](../getting-started/release-v0.5.8.md) |
| 현행 설치 | [관리자 설치](../getting-started/install.md) → [namespace 등록](../getting-started/namespaces.md) → [첫 VM](../getting-started/first-vm.md) |
| 기존 환경 변경 | [업그레이드·제거](../guides/upgrade-uninstall.md)와 대상 릴리스 안내 |
| 이미지 digest·chart version | 위 릴리스 JSON의 `images`, `chart` |
| 새 클러스터 배포의 전제 | [배포 기준과 v0.5.2 재현 절차](../getting-started/portable-deployment.md) |

v0.5.10은 중앙 Controller/Webhook과 시험 VM `dp-dev-20261105`의 Guest·Worker·helper·hook,
내부 Kubernetes Device Plugin을 갱신했다. 새 공개 이미지로 legacy CNN·MNIST 일부 학습, 수동 역전파 검산과 MLP·LSTM 회귀를 검증했다.
기존 GPU 할당량·namespace·TLS는 유지했다. 회수가 막힌 과거 Channel 3개와 외부 HAMi/DRA 등은
그대로 유지했으며, 전체 클러스터 구성 요소를 일괄 업그레이드한 것은 아니다.
새 별도 클러스터의 전체 GPU 설치 검증은 여전히 NOT_RUN이다.

이전 기록: [v0.5.9](../getting-started/release-v0.5.9.md), [v0.5.8](../getting-started/release-v0.5.8.md), [v0.5.7](../getting-started/release-v0.5.7.md),
[v0.5.6](../getting-started/release-v0.5.6.md), [v0.5.5](v0.5.5.md),
[v0.5.4](../getting-started/release-v0.5.4.md), [v0.5.3](v0.5.3-candidate.md),
[v0.5.2](../getting-started/release-v0.5.2.md).
구 Flyt PoC의 `v1.0.0`은 현재 VMWeave 릴리스가 아니다.

릴리스 시 `current.json`, 본문, chart, `versions.lock.yaml`을 함께 검토한다.
개발 중 chart 버전은 공개 릴리스와 달라도 되지만 chart와 lock은 일치해야 한다.
과거 릴리스 JSON·digest·증거는 수정하지 않는다.

선택 설치 구성인 **Device Plugin v0.1.2**은 Operator와 독립 버전이다.
[설치 안내](../guides/kubernetes-device-plugin.md),
[이미지·chart digest](../../deploy/releases/device-plugin-v0.1.2.json),
[실제 VM 검증](../../deploy/releases/evidence/v0.5.10/README.md),
[공개 릴리스](https://github.com/WoogiBoogi1129/VMWeave-GPU/releases/tag/device-plugin-v0.1.2)를 참조한다.
