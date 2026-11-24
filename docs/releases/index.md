# 현재 릴리스와 배포 기록

현재 공개 릴리스는 **v0.5.13**이며, Device Plugin은 기존 **0.1.4**를 유지한다.
2026-11-24의 게시·배포 결과는 [릴리스 기록](../../deploy/releases/v0.5.13.json)과
[검증 원본](../../deploy/releases/evidence/v0.5.13/README.md)에 있다.
기계 판독 진입점은 [current.json](../../deploy/releases/current.json)이다.

중앙 Operator는 `vmweave-system`의 하나를 유지하며 세 관리 namespace·TLS·mode를 보존했다.
이전 [Operator 통합 기록](../guides/operator-consolidation.md)과
[현재 배포](../../deploy/deployments/current.json)는 별도로 추적한다.

| 목적 | 확인할 자료 |
|---|---|
| v0.5.13 Worker HAMi 기본 정책 | [정책·적용·롤백 안내](../getting-started/release-v0.5.13.md) |
| v0.5.12 선택적 커널 제출 배치 | [릴리스·적용 옵션·롤백 안내](../getting-started/release-v0.5.12.md) |
| v0.5.11 고정 GPU 슬롯·미배치 Worker 회수 | [이전 릴리스 안내](../getting-started/release-v0.5.11.md) |
| 현행 설치 | [관리자 설치](../getting-started/install.md) → [namespace 등록](../getting-started/namespaces.md) → [첫 VM](../getting-started/first-vm.md) |
| 기존 환경 변경 | [업그레이드·제거](../guides/upgrade-uninstall.md)와 대상 릴리스 안내 |
| 이미지 digest·chart version | [Runtime](../../deploy/releases/v0.5.13.json), [Plugin](../../deploy/releases/device-plugin-v0.1.4.json) |

중앙 Controller/Webhook과 유휴 VM `dp-dev-20261105`의 Worker를 갱신했다.
새 Worker 생성 시 `GPU_CORE_UTILIZATION_POLICY=default`를 명시한다.
**실행 중 SM 한도 변경 기능은 배포 보류**했으며 CRD·제어 모듈·추가 HAMi 패치를 포함하지 않는다.
기존 GPU2 예약 25%, 1024 MiB, 1슬롯과 Guest·Device Plugin·helper·hook은 유지했다.

실제 Worker 프로세스의 정책과 GPU 복사·PTX 커널·SGEMM 정답을 확인했다.
`default`의 경쟁 판단·유휴 SM 활용 성능은 측정하지 않았으며 DRA 모니터 연동을 보증하지 않는다.
무관한 실행 Pod 119개, 기존 Draining Channel 3개와 공용 인프라 설정은 유지했다.
새 별도 클러스터 전체 설치와 일반 애플리케이션 성능 검증은 여전히 NOT_RUN이다.

v0.5.12의 선택적 커널 배치와 Broker 경로 최적화는 유지한다.
**커널 배치는 기본 비활성화**이며 애플리케이션의 bulk/direct 및 batch 옵션은 명시해야 한다.
이전 CNN·MLP·LSTM 등의 회귀 결과는 [v0.5.12 검증](../../deploy/releases/evidence/v0.5.12/README.md)에 있다.

이전 기록: [v0.5.12](../getting-started/release-v0.5.12.md), [v0.5.11](../getting-started/release-v0.5.11.md), [v0.5.10](../getting-started/release-v0.5.10.md),
[v0.5.9](../getting-started/release-v0.5.9.md), [v0.5.8](../getting-started/release-v0.5.8.md), [v0.5.7](../getting-started/release-v0.5.7.md),
[v0.5.6](../getting-started/release-v0.5.6.md), [v0.5.5](v0.5.5.md),
[v0.5.4](../getting-started/release-v0.5.4.md), [v0.5.3](v0.5.3-candidate.md),
[v0.5.2](../getting-started/release-v0.5.2.md).
구 Flyt PoC의 `v1.0.0`은 현재 VMWeave 릴리스가 아니다.

릴리스 시 `current.json`, 본문, chart, `versions.lock.yaml`을 함께 검토한다.
개발 중 chart 버전은 공개 릴리스와 달라도 되지만 chart와 lock은 일치해야 한다.
과거 릴리스 JSON·digest·증거는 수정하지 않는다.


선택 설치 구성인 **Device Plugin v0.1.4**는 Operator와 독립 버전이다.
[설치 안내](../guides/kubernetes-device-plugin.md),
[이미지·chart digest](../../deploy/releases/device-plugin-v0.1.4.json),
[실제 VM 검증](../../deploy/releases/evidence/v0.5.12/README.md),
[공개 릴리스](https://github.com/WoogiBoogi1129/VMWeave-GPU/releases/tag/device-plugin-v0.1.4)를 참조한다.
