# Kubernetes 설정

현재 지원 설치 입력은 `charts/vmweave-operator/values.yaml`과
`deploy/examples/vmweave/{review,active}.json`입니다.

| 입력 | 의미 |
|---|---|
| `management.namespaces` | 관리할 기존 namespace의 명시적 목록; 빈 목록 금지 |
| `mode` | `review`는 검증/status만 기록, `active`는 workload 생성·회수 |
| `activeModeAcknowledged` | active 설정의 명시적 선택 |
| `image.repository`, `image.digest` | Go Operator 이미지와 고정 digest |
| `tls.existingSecret`, `tls.caBundle` | 중앙 Webhook 서버 인증서와 CA |
| `controller.leaderElection` | system namespace의 Lease; 기본 true |
| `controller.replicas` | 기본 1; 복수 replica 장애 검증은 미완료 |
| `workloads.tolerations` | 사용자 namespace에 만드는 helper/Worker Pod tolerations |

API는 `vmweave.io/v1alpha1`이며 `GPUProfile`, `GPURequest`, `SharedMemoryChannel`,
`ChannelAttachment`를 제공합니다. 구조와 CEL 검증의 원본은
`operator/config/crd/bases/`입니다. chart CRD 사본은 CI에서 동일성을 확인합니다.
상세 VM/PVC/Request UID 입력은 [첫 VM](../getting-started/first-vm.md)을 따릅니다.

Controller/Webhook용 재사용 ClusterRole을 사용자 namespace의 RoleBinding으로 연결합니다.
클러스터 전체 workload 쓰기 권한은 부여하지 않습니다. active Controller에는 자기 관리 범위에서
Worker별 Role/RoleBinding을 생성할 권한이 있습니다. 이 권한으로 만드는 Role은 Controller 자신이
이미 가진 Channel/Attachment 권한의 부분집합입니다.

일반 사용자가 승인 GPUProfile을 변경할 권한은 조직 RBAC에서 제한해야 합니다.
관리자 등록·해제는 [namespace 운영](../getting-started/namespaces.md), API 이전은
[이전 가이드](../guides/migrate-to-vmweave-api.md)를 확인하세요.

구 `flyt.dev` CRD와 Python Controller 입력은 과거 실험·회수 호환 경로에만 남아 있습니다.
