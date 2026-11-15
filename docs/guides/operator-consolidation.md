# 중앙 Operator 통합 기록

2026-11-15에 `gpu-4`의 두 Operator 설치를 `vmweave-system`의 Helm release
`vmweave` 하나로 통합했다. Controller 1개와 Webhook 1개는 같은 Operator의 구성 요소다.
두 구성 요소 모두 v0.5.11이며, 이미지 digest와 chart 0.5.11은 변경하지 않았다.

| 항목 | 통합 후 상태 |
|---|---|
| system namespace / Helm release | `vmweave-system` / `vmweave`, revision 21 |
| 관리 namespace | `vmweave-test-a`, `vmweave-test-b`, `vmweave-nested-k8s` |
| 제거한 설치 | `nested` release, `vmweave-nested-system`, 해당 RBAC·Webhook |
| VM 내부 Kubernetes | 같은 중앙 Operator가 VM과 GPU Channel을 관리 |
| VM 내부 일반 ML 프로세스 | 같은 중앙 Operator가 VM과 GPU Channel을 관리 |
| 선택 구성 | VM 내부 GPU Pod 할당에는 Device Plugin v0.1.3 사용 |

Operator는 Guest 안의 실행 방식을 구분해서 설치할 필요가 없다. Device Plugin은 Guest
Kubernetes의 GPU 자원 광고·할당을 담당하며, 별도의 VMWeave Operator가 아니다.

현재 배포 상태는 [배포 진입점](../../deploy/deployments/current.json),
[배포 기록](../../deploy/deployments/operator-consolidation-20261115.json),
[검증 자료](../../deploy/deployments/evidence/operator-consolidation-20261115/README.md)에 있다.
2026-11-13 [릴리스 기록](../../deploy/releases/v0.5.11.json)에 있는 두 설치는 당시의 사실이며 그대로 보존한다.

## 전환 절차와 적용 범위

이번 전환은 같은 버전의 Controller 사이에서 **기존 관리 책임을 넘긴 작업**이다.
관리 대상 제거, API schema 변경, backend 변경이나 GPU 할당 회수가 아니다.
기존 Controller는 상태를 Channel·Attachment에 저장하고 Worker의 소유자는 Channel이다.
새 Controller도 동일한 객체를 읽으며, Worker의 ServiceAccount와 할당 식별자는 유지된다.

1. 두 release의 values·manifest와 대상 객체를 비공개 경로에 백업하고 공개 chart의 SHA256을 확인했다.
2. 두 release에 `maintenance.enabled=true`를 적용하고 Controller Pod가 모두 종료됐는지 확인했다.
3. 중앙 release의 관리 목록에 `vmweave-nested-k8s`를 추가했다. Controller는 정지한 채 RBAC와 Webhook을 먼저 준비했다.
4. 기존 `nested` release의 Webhook 등록을 해제했다. Attachment status는 Controller의 namespace/ServiceAccount를 검증하므로, 서로 다른 계정을 허용하는 두 Webhook을 남긴 채 재개하지 않았다.
5. 세 namespace의 권한·admission 검사를 통과한 뒤 중앙 Controller만 재개했다.
6. reconcile·기존 객체 보존·GPU Pod 실행을 확인하고 `nested`를 제거했다. 이전 system namespace에 TLS Secret·Lease·기본 객체만 남았는지 전 API 리소스를 조사한 뒤 namespace도 제거했다.

서로 다른 system namespace의 Controller는 서로 다른 leader Lease를 사용한다.
따라서 leader election만으로 중복 관리를 방지할 수 없다. 전환 중 두 Controller의 관리 범위를
겹쳐 활성화해서는 안 된다. Webhook의 Recreate 교체 중에는 admission 요청이 일시적으로 실패할 수 있다.
실행 중이던 VM과 Worker는 재시작하지 않았다.

이 절차를 다른 버전이나 backend의 통합에 그대로 적용하지 않는다.
관리에서 namespace를 제외하거나 데이터를 삭제할 때는 기존
[회수·제거 절차](upgrade-uninstall.md)를 따른다. 전환 실패 시 Controller를 정지한 상태에서
기존 RBAC·Webhook의 관리 범위와 계정 검증을 먼저 복원하고, 각 namespace에 Controller가
하나만 활성화되도록 재개한다.

## 검증 결과와 남은 사항

- VM·VMI·Channel·Attachment·Pod·Request·Profile 47개의 UID, spec, 소유 관계, finalizer가 보존됐다.
- 실행 중인 두 VMI와 GPU Worker의 식별자·컨테이너 재시작 횟수, GPU allocation/generation이 유지됐다.
- 세 namespace의 권한과 Channel admission, 미등록 namespace 권한 거부, 새 Controller의 Attachment 갱신 허용, 이전 Controller 거부, VMI binding 변경 거부 등 10개 검사가 통과했다. 요청은 서버 dry-run이었다.
- 중앙 Controller에서 실제 reconcile 48회 관측 시 오류·panic·timeout은 0이었다.
- `dp-dev-20261105` 내부 Kubernetes에서 `vmweave.io/gpu: 1` Pod를 실행해 SGEMM 2×2 전체 결과 검증을 통과했다. 시험 namespace는 제거했다.
- 기존 `Draining / AwaitingDetachEvidence` Channel 3개는 그대로다. 통합은 이 회수 문제를 해결한 작업이 아니며 finalizer를 강제 제거하지 않았다.

이번 작업에서 새 VM 생성과 2슬롯 동시 GPU 회귀는 재실행하지 않았다.
해당 기능의 기존 검증 범위는 [v0.5.11 안내](../getting-started/release-v0.5.11.md)를 참조한다.
