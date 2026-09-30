# 중앙 VMWeave 제어기 전환 분석 및 수정 계획

> **이 문서는 이전 검토안이다.** [최종 Go Operator·API 전환 계획](operator-migration-plan.md)이
> 본문의 Python 유지·기존 API 유지 결정을 대체한다. 아래 내용은 조사 이력이며 현재 실행할 설치 지침이 아니다.

작성: 2026-09-30. 분석 기준: `c3c07c9`. 상태: **설계 제안이며 미구현**.
이번 작업은 저장소 분석과 계획 작성이다. 기존 제어기 코드와 클러스터 배포는 변경하지 않았다.

재정리 원칙: **클러스터 관리자가 중앙 제어기를 한 번 설치하고, 사용자는 자기 namespace에
VM 관련 리소스만 배포한다.** 사용자 namespace 추가는 제어기 재설치가 아니라 관리 범위와
접근권한 등록이다. 아래 설치 문서 정형화도 이 구분을 기준으로 한다.

## 결론과 목표

`vmweave-system`에 controller와 webhook을 한 번 설치하고, 명시적으로 등록한 여러
workload namespace의 VMWeave 리소스를 관리한다. VM, VMI, Channel, Request, Profile,
Attachment, Worker, prepare/reclaim Pod, PVC는 각 workload namespace에 둔다.
중앙 배포는 하나의 관리 주체를 뜻하며, 향후 HA Pod 복제본 수와는 별개이다.

namespace별 controller도 유효한 Kubernetes 배포 방식이다. 현재 문제는 Kubernetes API를
쓰지 않는다는 것이 아니라, 설치 위치와 관리 범위가 코드 전반에서 결합되어 있다는 점이다.
Manager의 관리 범위와 CRD의 Namespaced/Cluster 범위는 독립적이다.
[Kubebuilder manager scope](https://book.kubebuilder.io/reference/manager-scope.html).

```text
vmweave-system
  controller ──┬── team-a: VM / Request / Profile / Channel / PVC
  webhook      │              └─ Attachment / prepare / Worker / reclaim
  Service/TLS  └── team-b: VM / Request / Profile / Channel / PVC
  ServiceAccounts             └─ Attachment / prepare / Worker / reclaim
  [후속: leader-election Lease]

kubevirt: KubeVirt 구성 유지
kube-system 또는 기존 설치 위치: HAMi 구성 유지
```

첫 전환은 Python 제어기를 유지한다. Go/controller-runtime 재작성, API group 이름 변경,
클러스터 범위 Profile 도입, CUDA/SHM ABI 변경을 함께 묶지 않는다. 언어 전환이 중앙 관리의
필수 조건은 아니다. watch/cache/queue/leader election은 별도의 운영 개선 단계로 명시한다.

## 조사 범위와 현재 제약

현재 경로인 `runtime/shm/control`, Helm/CRD, 설치·실험 도구, 이미지, CPU/통합 테스트,
CI, 현재 docs를 조사했다. `legacy/`와 저장된 실험 결과는 이력과 의존성 확인에 사용했으며
그 안의 코드 사본을 현재 제품 구현으로 취급하지 않았다. CUDA 구현 전체의 정확성을
재검증한 분석은 아니며, 중앙 관리 전환의 영향 범위에 초점을 맞췄다.

| 영역 | 현재 확인 사항 | 필요한 변경 |
|---|---|---|
| `settings.py` | `FLYT_NAMESPACE` 하나만 검증 | 설치 namespace와 관리 namespace 목록 분리 |
| `kube.py` | 생성 시 namespace를 고정하고 모든 namespaced URL에 사용 | 명시적 namespace client/context 도입 |
| `control_plane.py` | 단일 namespace Channel 목록을 순회, 실패 시 전체 루프 backoff | namespace별 처리 및 실패 격리, 이후 객체별 queue |
| `channel_controller.py` | 자식 metadata는 Channel namespace를 사용하나 API URL은 전역 client에 의존 | Channel의 namespace와 client가 일치함을 보장 |
| `admission.py` | AdmissionReview namespace 대신 `API()`의 기본 namespace 사용 | 요청 namespace 검증 및 그 namespace에서 참조 조회 |
| `admission.py` 인증 | controller와 Worker SA를 모두 workload namespace로 가정 | 중앙 controller SA와 현지 Worker SA를 분리 |
| VMI admission | SHM annotation 없는 신규 VMI 거부, UPDATE는 일반 VMI의 배치 변경도 제한 | 일반 VM과 관리 대상 VM의 분기 및 우회 방지 |
| `observe.py`, `supervisor.py` | Worker도 동일 `API()`를 사용 | Worker의 현지 namespace 계약 유지 |
| Helm RBAC | release namespace의 Role/RoleBinding, Node/PV만 ClusterRole | 중앙 SA에 대상 namespace별 권한 부여 |
| Helm webhook | `namespaceSelector`가 release namespace 한 곳 | controller와 동일한 관리 범위 사용 |
| Helm Deployment | 1 replica, Recreate, leader election 없음 | 초기 유지, HA는 Lease/동시성 검증 후 도입 |
| CRD | 4종 모두 Namespaced, 참조는 name+UID | 동일 namespace 참조를 유지하고 문서화 |
| 설치/TLS | `--namespace` 하나로 모든 위치를 표현 | control-plane namespace와 workload 목록 분리 |
| 테스트 | 단일 namespace fake/client 중심 | 서로 다른 namespace의 동명 객체 검증 필수 |
| 실험 도구 | `flyt-evidence` 등 하드코딩 존재 | 현행 도구의 입력 분리, 원본 증거는 보존 |

주요 근거 파일:
[API](../../runtime/shm/control/kube.py),
[reconcile](../../runtime/shm/control/channel_controller.py),
[admission](../../runtime/shm/control/admission.py),
[RBAC](../../charts/flyt-control-plane/templates/rbac.yaml),
[설치 안내](../getting-started/cpu-control-plane.md).

## 설계 결정

### 1. 위치, 범위, 실행 모드 분리

초기 권장 설정 예시는 다음과 같다. **아래 필드는 새로 구현할 제안이며 현재 사용 불가하다.**

```yaml
mode: active
activeModeAcknowledged: true
management:
  namespaces: [team-a, team-b]
controller:
  replicas: 1
```

- control-plane namespace는 Helm release namespace이며 기본 설치 예시는 `vmweave-system`이다.
- `management.namespaces`는 명시적 목록이며 빈 목록은 전체 클러스터를 뜻하지 않는다.
  실수로 전체 범위에 권한을 부여하지 않도록 설치 검증에서 거부한다.
- controller, webhook, RBAC가 하나의 설정에서 동일 목록을 사용한다.
- 초기 버전은 목록 기반 다중 namespace 관리로 한정한다. workload namespace를 사용자가
  먼저 만들고, 설치 도구가 존재 여부·권한·이전 controller 충돌을 확인한다.
- 전역 `mode`는 초기에는 유지한다. review는 격리된 테스트 클러스터에서 검증하며,
  같은 namespace에 review/active release를 겹쳐 배포하지 않는다. namespace별 실행 모드는 후속 기능이다.
- 기존 `FLYT_NAMESPACE`는 Worker의 workload namespace 계약으로 유지한다.
  controller에는 `FLYT_CONTROL_PLANE_NAMESPACE`, `FLYT_MANAGED_NAMESPACES`를 분리 도입한다.
- 동적 label selector 및 전체 namespace 자동 관리는 후속 확장이다. label 선택은 RBAC 권한
  경계가 아니므로 selector만으로 권한 격리를 보장한다고 설명하지 않는다.

### 2. API와 reconciliation

- 전송 계층과 `NamespacedAPI(namespace)`를 분리한다. `for_namespace(ns)`는 새로운 불변
  context를 반환한다. 공유 `api.namespace`를 반복문/HTTP 스레드에서 바꾸지 않는다.
- GET/CREATE/UPDATE/STATUS/DELETE 모두 같은 context를 사용한다. 쓰기 전 객체의
  `metadata.namespace` 불일치를 거부한다. cluster-scoped Node/PV 경로는 별도 메서드로 둔다.
- 큐·캐시 식별자는 `(namespace, name)`이고 세대 식별은 기존 UID/resourceVersion을 유지한다.
  UID 검증을 단순 이름 비교로 바꾸지 않는다.
- Channel 처리마다 그 Channel의 namespace context를 넘겨 VM/Request/Profile/PVC 및
  Attachment/Pod를 조회한다. 다른 namespace로 fallback 검색하지 않는다.
- 초기 polling은 namespace별 오류/backoff를 분리하고 공정하게 순회한다. 한 namespace의
  403/429/5xx나 오래된 Channel이 다른 namespace 처리를 멈추지 않도록 처리량을 제한한다.
- 목록 pagination을 지원한다. 후속 watch 구현에서는 reconnect, resourceVersion,
  410 Gone 후 relist, 주기 resync, 삭제 이벤트를 처리한다.
- Released 이력의 반복 작업 생략은 유지하되, deletionTimestamp가 있으면 finalizer 정리를 한다.
- 신규 할당과 기존 할당 회수를 구분한다. 관리 해제/삭제 진행 중에는 신규 할당을 막고
  기존 할당의 detach·reclaim은 완료해야 한다.

### 3. 리소스 배치와 CRD 계약

기존 네 종류 CRD는 Namespaced로 유지한다. Channel의 `vmRef/requestRef/pvcRef`, Request의
`vmRef/profileRef`, Attachment의 `channelRef`는 모두 자신이 속한 namespace의 객체를 가리킨다.
중앙 controller가 여러 namespace를 관리하는 데 cross-namespace 참조 필드는 필요하지 않다.

Worker와 prepare/reclaim Pod도 workload namespace에 유지한다. PVC 참조와 Worker SA/Role,
Channel ownerReference를 그대로 같은 namespace 안에서 연결한다. namespaced owner를 다른
namespace의 자식에 연결하면 안 된다.
[Kubernetes ownerReference 규칙](https://kubernetes.io/docs/concepts/overview/working-with-objects/owners-dependents/).

`FlytGPUProfile`의 중앙 카탈로그화는 별도 API 설계로 미룬다. 초기에는 각 namespace에
관리자가 승인한 Profile을 두고, 사용자에게 Profile 승인·수정 권한을 자동 부여하지 않는다.
namespace별 Profile의 상한은 클러스터 전체 GPU 총량 예약을 뜻하지 않는다. GPU 배치는
기존 HAMi 경로를 유지하고 다중 namespace 동시 실행으로 검증한다.

CRD의 group/version/kind, UID 참조 및 상태 구조는 호환 유지한다. 스키마 설명을 바꿀 때는
`deploy/shm/`와 `charts/flyt-control-plane/crds/` 복사본을 함께 갱신한다.

### 4. RBAC

중앙 controller/webhook ServiceAccount는 `vmweave-system`에 둔다. 재사용 가능한
ClusterRole을 정의하되, 초기 기본은 대상 namespace마다 RoleBinding으로 연결한다.
이 경우 namespaced list/watch를 사용하고, cluster-wide list가 가능하다고 가정하지 않는다.
[Kubernetes RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/).

| 주체 | 권한 범위 |
|---|---|
| 중앙 controller | 대상 namespace의 Channel 상태/finalizer, Attachment, VM 수정, 현지 Pod·SA·Role·RoleBinding 관리 |
| 중앙 controller의 cluster reader | 현재 필요한 Node/PV 읽기, 추가 설계에 필요한 Namespace 조회만 |
| 중앙 webhook | 대상 namespace의 검증용 CR·VM/VMI·Pod 읽기; workload 변경 불가 |
| Worker | 자신의 Channel 읽기와 해당 guest/worker Attachment 보고만 |
| 사용자 | 승인된 요청·채널 생성 등 명시적으로 정한 권한; Profile 승인 권한과 구분 |

불필요한 Secrets 접근, wildcard, `cluster-admin`, `bind/escalate`를 추가하지 않는다.
동적으로 만드는 Worker Role의 권한이 controller 자신의 권한 내에 있는지 API 서버에서
확인한다. ownerReference의 `blockOwnerDeletion`에 필요한 소유자 삭제 권한도 검증한다.
watch 도입 시에만 관련 watch 권한을 추가하고, review용 역할에는 workload 쓰기를 넣지 않는다.

workload namespace와 VM/PVC를 중앙 Helm release 소유로 만들지 않는다. 대상 namespace의
접근 RoleBinding은 설치 도구가 별도 관리하고, drain 완료 전에 제거하지 않는다.
namespace 라벨/모드/허용 목록의 변경은 운영자 권한으로 제한한다.

### 5. Webhook 범위와 인증

- `request.namespace`를 기준으로 client를 선택하고 object metadata namespace와 대조한다.
  지원 kind/operation/subresource와 허용 관리 범위도 확인한다.
- 중앙 controller 신원은 정확한
  `system:serviceaccount:<control-plane-ns>:<controller-sa>`로 비교한다.
  Worker 신원은 `<request namespace>:<channel>-worker`이며 기존 Pod UID·세대 검증을 유지한다.
- 다른 namespace의 동명 Worker SA는 보고를 승인받을 수 없어야 한다.
- webhook Service, TLS Secret, 인증서 SAN은 control-plane namespace에만 둔다.
- 초기 `namespaceSelector`는 `kubernetes.io/metadata.name In [관리 목록]`으로 생성한다.
  controller와 selector가 불일치하면 설치 검증을 실패시킨다.
- 관리 namespace에서도 일반 VMI CREATE/UPDATE/migration을 허용한다. VMWeave 대상 여부는
  annotation 하나만으로 판단하지 않고, 기존/새 객체의 binding, 소유 VM UID,
  해당 VM을 가리키는 Channel을 함께 확인한다. annotation 제거로 검증을 우회할 수 없어야 한다.
- VMWeave VMI의 기존 binding 불변성, 배치, hook/PVC, migration 거부는 유지한다.
  유효한 관리 대상 판정이 불가능한 API 오류에서는 관리 대상 요청을 fail-closed 처리한다.
- 사용자 수정이 가능한 object label만으로 필수 검증을 선택하지 않는다.
  [공식 admission 문서](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/).
- 초기에는 webhook 장애가 선택된 namespace의 관련 요청에도 영향을 줄 수 있음을 명시한다.
  서버 내부에서 일반 VM을 허용하는 것만으로 webhook 서비스 장애의 영향까지 제거되지는 않는다.

### 6. 회수, namespace 제거, 장애 복구

현재 `channel_controller.py`는 drain 중 새 `<channel>-reclaim` Pod를 생성한다.
그러나 Terminating namespace에는 새 객체를 생성할 수 없다. 중앙 배포로 옮기는 것만으로
이 문제가 해결되지는 않는다.
[Namespace lifecycle](https://kubernetes.io/docs/tasks/administer-cluster/namespaces/).

초기 지원 절차는 **등록 유지 → 신규 요청 차단 → drain → detach 증거 확인 → reclaim 완료 →
Channel/Pod finalizer 해소 → 관리 대상 해제 → namespace 삭제**로 정한다.
삭제 사전 점검 명령은 진행 중 allocation과 finalizer가 있으면 실패해야 한다.
관리 목록에서 namespace를 바로 빼거나 중앙 release를 먼저 uninstall하지 않는다.

namespace 직접 DELETE의 자동 회복은 초기 지원 범위로 주장하지 않는다. Terminating 상태와
회수 Pod 미존재를 탐지해 명확한 Condition/이벤트로 보고하고, detach 증거를 보존한다.
강제 finalizer 제거를 정상 복구 절차로 삼지 않는다. 직접 DELETE까지 지원하려면 미리 존재하는
노드 정리 서비스 등 별도 회수 수단이 필요하며, PVC를 system namespace Pod에 단순 연결하는
방식은 해결책이 아니다. 이 기능은 별도 설계·장애 시험 후 도입한다.

Released Channel의 삭제도 현재는 증거/기존 reclaim Pod에 의존하므로, 회수 완료 증거의
내구성과 자식 GC 순서를 시험해야 한다. 삭제 성공만을 위해 증거 요건을 완화하지 않는다.

### 7. HA와 운영 관측

초기 다중 namespace 버전은 controller 1개와 Recreate를 유지한다. namespace 수가 늘어도
controller 배포를 추가하지 않는다. 기존의 모든 active release와 관리 범위 중복을 검사한다.

후속 단계에서 namespaced list/watch + 객체별 rate-limited queue, Lease leader election,
Webhook 다중 replica/RollingUpdate를 도입한다. Lease 상실 시 새 작업을 중단하고 진행 중
API 변경을 종료하며, deterministic 자식 이름·UID·RV precondition과 멱등성을 검증한다.
Lease만 추가하고 SHM 파일 부작용까지 완전한 fencing이 된다고 간주하지 않는다.
[Kubernetes Leases](https://kubernetes.io/docs/concepts/architecture/leases/).

로그는 namespace/name/UID를 일관되게 포함한다. health는 프로세스 생존, API 접근,
등록 namespace의 권한/동기화 상태를 구분한다. 하나의 불량 namespace가 정상 namespace의
reconcile을 멈추거나 모든 webhook endpoint를 불필요하게 내리지 않게 설계한다.
queue 지연, API 오류, 관리 대상 수, drain 대기 수를 측정하고 UID를 metric label로 쓰지 않는다.

## 파일별 작업과 실행 순서

| 단계 | 변경 파일/범위 | 완료 기준 |
|---|---|---|
| 1. namespace 계약 | `settings.py`, `kube.py`, 신규 scope 모듈, API unit tests | 설치 위치와 대상 위치 분리, namespace 없는 쓰기/불일치 차단 |
| 2. 중앙 reconcile | `control_plane.py`, `channel_controller.py`, `observe.py`, `health.py` | 두 namespace 동명 Channel 독립 처리, 오류/backoff 격리, Worker 호환 |
| 3. admission | `admission.py`, webhook template, 인증/VM 분류 tests | 중앙 SA 인증, 현지 Worker 보고, 일반 VM 공존, annotation 제거 우회 차단 |
| 4. 배포·설치 | chart values/schema/RBAC/deployments/helpers, `install-control-plane.py`, `create-review-tls.py`, 접근 등록·해제 도구 | 중앙 release 한 번 설치, 대상 추가 시 controller 추가 없음, 안전한 관리 해제 |
| 5. 운영·도구 | `prepare-evidence-vm.py`, 현행 smoke/학습/campaign 도구, 이미지 빌드 | namespace 입력화, 기존 Worker env/이미지 호환, 회수 사전 점검 |
| 6. 통합 검증·문서 | `tests/integration`, CI, getting-started/architecture/reference/operations/roadmap | 두 tenant 및 미관리 namespace 시험, 새 설치/해제 안내, 이전 문서와 구분 |
| 7. 실제 이전 | 새 클러스터 검증 이후 기존 실험 namespace별 전환 | UID/PV 데이터 보존, 동시 writer 없음, 이전/복구 기록 |
| 8. 운영 확장 | watch/cache/queue, Lease, HA chart/장애 tests | 리더 전환 중 중복 할당·회수 없음, 장애 시 영향 측정 |

1~6은 하나의 중앙 관리 기능으로 통합 검증 후 릴리스한다. 중간 커밋의 코드/차트만
부분적으로 실험 클러스터에 적용하지 않는다. 8은 중앙 관리와 별도로 검증하는 운영 개선이다.
Go/controller-runtime 전환은 8의 구현 비용과 Python 유지 비용을 비교해 별도 결정한다.

설치 도구는 control-plane namespace, 관리 목록, TLS, RBAC, webhook 준비를 구분한다.
중앙 배포 완료 전에 workload 접수를 열지 않으며, upgrade 중 webhook을 무조건 해제하지 않는다.
uninstall은 관리 workload를 삭제하지 않고 먼저 allocation/finalizer 잔존 여부를 검사한다.

`scripts/render-shm.py`는 이미 과거 실험 경로로 명시되어 있다. 새 기능의 설치 경로는 Helm에
집중하고 이 스크립트가 새 중앙 구조를 지원한다고 표시하지 않는다.
`experiments/evidence/results/**`, `legacy/**`의 원본·해시·당시 namespace는 보존한다.
현행 재사용 도구만 namespace 인자를 추가하며 새 검증 결과는 별도 디렉터리에 저장한다.

## 설치 문서 정형화 계획

### 사용자에게 제공할 설치 흐름

중앙 설치를 공통 절차로 만들고 CPU/GPU를 별도 controller 설치 방법으로 설명하지 않는다.
CPU review는 동일 패키지의 개발 검증 설정이며, 일반 사용자의 필수 선행 설치가 아니다.
GPU 사용자는 준비된 인프라 위에 중앙 active release를 한 번 설치하고 VM 배포로 진행한다.
review와 active의 기존 권한 차이는 유지하되 테스트 모드 선택과 제품 설치 구조를 구분한다.

| 순서 | 수행 주체 | 작업 | 결과 |
|---|---|---|---|
| 1. 인프라 준비 | 클러스터 관리자 | 지원 조합, KubeVirt, NVIDIA/HAMi, SHM용 local PV·노드 준비 확인 | 사전 점검 보고서 |
| 2. 중앙 설치 | 클러스터 관리자 | CRD, 중앙 SA/RBAC, TLS, controller/webhook 설치 | `vmweave-system`에 release 1개 |
| 3. 관리 대상 등록 | 클러스터 관리자 | workload namespace 생성/선택, 관리 목록·RoleBinding·webhook 범위 반영 | 사용자 namespace에 controller/webhook 없음 |
| 4. 사용자 환경 준비 | 관리자/사용자 | 승인 Profile, PVC, 이미지 접근, Guest·hook 입력 준비 | 해당 namespace의 VM 실행 준비 |
| 5. VM 배포 | 사용자 | Halted VM → GPURequest → Channel 생성, BackingReady 확인 후 VM 시작 | 현지 virt-launcher 및 Worker 생성 |
| 6. 검증·종료 | 사용자 | Ready/mapping 확인, GPU smoke, drain·detach·Released 확인 | 실행 및 회수 결과 |
| 7. 관리 해제·제거 | 클러스터 관리자 | 할당·finalizer 검사 후 대상 해제 또는 중앙 release 제거 | 데이터 보존 여부가 명시된 제거 결과 |

3은 중앙 설치 시 초기 namespace 목록을 지정해 함께 실행할 수 있다. 이후 대상 추가는
동일 설치 도구의 설정 갱신으로 처리하며 사용자에게 Helm release를 추가하라고 안내하지 않는다.
관리 목록 변경은 RBAC 준비 → webhook 준비 → controller 처리 개방 순서로 적용하고,
제거는 drain → controller 처리 종료 → webhook/권한 제거 순서로 수행한다.
동일 Helm upgrade 안에서 모든 변경이 원자적으로 일어난다고 가정하지 않고 도구가 단계를 조율한다.

### 정형 문서 목차와 기존 문서 처리

아래 신규 경로는 구현할 문서의 계획이며 아직 생성된 설치 안내가 아니다.

| 문서 | 역할과 수정 내용 |
|---|---|
| `docs/getting-started/index.md` | 단일 진입점. 관리자 중앙 설치와 사용자 VM 배포 경로를 구분 |
| `docs/getting-started/prerequisites.md` (신규) | 검증 버전, 권한, 인프라·스토리지·이미지 사전 점검 |
| `docs/getting-started/install.md` (신규) | 중앙 release 설치의 유일한 기준 절차; TLS·RBAC·readiness 포함 |
| `docs/getting-started/namespaces.md` (신규) | 대상 namespace 등록·확인·안전한 해제; 제어기 재설치 없음 |
| `docs/getting-started/first-vm.md` (신규) | 현지 Profile/PVC/VM/Request/Channel 배포, 시작·검증·회수 |
| `docs/getting-started/cpu-control-plane.md` | 중앙 review 검증 안내로 전환. 공통 설치 문서를 참조하고 설치 명령 복제 제거 |
| `docs/getting-started/gpu.md` | GPU 인프라/Guest/이미지 준비에 집중. 별도 controller 설치 지시 제거 |
| `docs/guides/operations.md` | system 로그와 workload 상태 조회 분리, 오류·재시작·회수 점검 |
| `docs/guides/upgrade-uninstall.md` (신규) | upgrade, TLS 회전, drain, uninstall, PVC/PV·CRD 보존, rollback |
| `docs/guides/migrate-central-controller.md` (신규) | 기존 namespace별 설치에서 중앙 배포로 이전하는 전용 절차 |
| `docs/reference/configuration.md` | 설치/관리/workload namespace, 모드, 권한, values 및 기본값의 기준 |
| `docs/architecture/index.md`, `lifecycle.md` | 중앙 제어·현지 실행 구조와 소유 관계, 관리 해제 수명 주기 |
| `README.md`, `docs/index.md`, `mkdocs.yml` | 새 진입점·탐색 경로 반영 |
| `docs/installation/*`, `legacy/docs/*`, 기존 증거 | 과거 설치 기록임을 유지; 새 제품 설치 명령의 근거로 사용하지 않음 |

각 절차는 같은 형식으로 작성한다: **목적/수행 주체 → 사전 조건 → 입력값 → 실행 →
예상 결과와 확인 명령 → 실패 시 조치 → 정리/보존 대상**. 검증된 지원 범위와 미검증 항목을
구분하고, 한 문서에서 `YOUR_NAMESPACE`가 system과 workload 둘 다를 뜻하지 않게 한다.

### 명령과 배포 산출물 규칙

- 예제의 control-plane namespace는 `vmweave-system`, release는 `vmweave`, 사용자
  namespace는 `team-a`/`team-b`로 통일한다. `flyt-evidence` 등은 실험 이력에서만 기본값으로 남긴다.
- 기존 chart 이름·API group·환경변수·이미지 식별자는 호환성을 위해 유지한다.
  예제 release를 `vmweave`로 정해도 생성 리소스 이름에 `flyt`가 남을 수 있음을 설명한다.
  조회 명령은 이름을 추측하지 않고 실제 helper 규칙 또는 release/component label을 사용한다.
- 공통 변수 이름은 `CONTROL_PLANE_NAMESPACE`, `WORKLOAD_NAMESPACE`, `RELEASE_NAME`,
  `CONTROL_PLANE_IMAGE_DIGEST`로 통일한다. TLS 이름/이미지/관리 목록은 파일 한 곳에서 입력한다.
- 공식 설치 경로는 **Helm chart + `scripts/install-control-plane.py`**로 통일한다.
  CRD 적용과 최초 webhook 등록 순서를 조율하는 현재 도구를 확장한다. raw Helm 명령은
  해당 절차를 이해한 고급 사용자용으로 분리하고 동등하게 검증되지 않은 대체 절차를 나열하지 않는다.
- 현행 `--namespace`는 control-plane 위치라는 의미를 명시하고,
  `--control-plane-namespace`라는 명확한 이름을 추가하는 방안을 채택한다.
  기존 옵션은 호환 alias로 유지하되 두 옵션이 충돌하면 실패한다.
- 대상 namespace 목록은 values의 `management.namespaces`를 단일 기준으로 사용한다.
  별도 CLI 입력이 있다면 최종 values로 합친 결과를 표시하고 RBAC/webhook/controller에 동일하게 반영한다.
- `deploy/examples/central/`에 최소 review/active values와 사용자 리소스 예제를 제공한다.
  VM/Request/Profile/PVC UID는 생성 후 조회하여 Channel을 렌더링하는 도구로 연결한다.
  이전 실험의 UID·IP·GPU UUID·호스트 경로를 복사하도록 안내하지 않는다.
- registry pull Secret은 control-plane용과 workload용을 구분한다. system namespace의
  Secret만 생성하면 다른 namespace의 Worker도 사용할 수 있다고 설명하지 않는다.
- TLS 개발용 CA와 운영 인증서 경로를 구분하고 Service DNS는 system namespace 기준으로 생성한다.
  현재 미실증 cert-manager 경로를 검증 없이 표준 운영 경로로 승격하지 않는다.
- 노드 local PV 준비는 인프라 절차, 현지 PVC 사용은 사용자 절차로 구분한다.
  `Retain`인 PV의 데이터 삭제·재사용은 namespace 제거와 별개임을 명시한다.
- kubectl 명령은 항상 system 또는 workload namespace를 명시한다. 중앙 제어기 로그와
  사용자 Channel/Worker 상태 확인을 다른 명령 블록으로 제시한다.
- 이미지 digest를 포함한 준비 가능한 예제로 시험한다. build/publish 개발 절차는 별도 링크로
  옮기되, 검증된 배포 이미지가 공개되지 않았다면 그 준비 과정을 필수 조건으로 명시한다.

### 문서 완료 기준

1. 빈 테스트 클러스터에서 공통 안내만 따라 중앙 설치가 완료된다.
2. 같은 중앙 release로 team-a/team-b의 동명 VM 관련 리소스를 관리한다.
3. namespace를 추가해도 controller/webhook Deployment는 system namespace에만 존재한다.
4. 사용자 절차에는 controller 설치, CRD 설치, ClusterRole 생성 명령이 없다.
5. 일반 VM과 VMWeave VM의 공존, 정상 회수, 관리 대상 해제, 중앙 upgrade/uninstall이 검증된다.
6. CPU review는 GPU 실행 성공과 구분되며 active 설치의 의무적인 선행 release가 아니다.
7. 예제 values는 schema/Helm render/lint, 리소스 예제는 API server validation,
   문서 링크는 strict build, 실제 순서는 통합 테스트로 검증한다.
8. 과거 결과 원문·UID·해시는 유지하며 새 경로는 신규 검증 결과에 연결한다.

현재 지원하지 않는 명령으로 기존 설치 문서를 미리 덮어쓰지 않는다. 구현과 예제 검증이
완료되는 릴리스에서 기준 설치 문서·탐색 메뉴·호환 안내를 함께 전환한다.

## 필수 검증 행렬

| 시험 | 통과 조건 |
|---|---|
| team-a/team-b에 동명 VM·Channel·PVC·Request·Profile | 조회/수정/삭제/이벤트가 상대 namespace에 침범하지 않음 |
| 두 namespace GPU 동시 실행 | 각 quota·mapping·회수 독립, 기존 HAMi 정책 준수 |
| 미등록 namespace | 중앙 controller가 workload를 생성·수정하지 않음; RBAC로도 차단 |
| 일반 VM + SHM VM 혼재 | 일반 VM 실행/배치 수정 허용, SHM binding·migration 제한 유지 |
| 중앙 controller SA와 동명 현지 SA | 중앙 SA만 controller 보고로 인정 |
| team-a Worker가 team-b Attachment 보고 | API RBAC 및 webhook 검증에서 거부 |
| annotation 삭제/복제, 오래된 UID, 동명 재생성 | binding 우회·잘못된 회수·기존 allocation 재사용 없음 |
| 한 namespace의 권한 오류/429/5xx | 다른 namespace reconcile 지속; 파괴적 상태 전환 없음 |
| PVC/Pod/VMI 누락, 노드 단절 | 누락을 detach 증거로 취급하지 않음 |
| 관리 해제/namespace 삭제 | drain 미완료 시 사전 점검 실패, 정상 회수 후 해제 성공 |
| 이미 Terminating인 namespace | 신규 reclaim 생성 불가를 명확히 보고, 증거 보존, 지원 한계 노출 |
| release upgrade/uninstall/롤백 | webhook 인증·범위 일치, 이중 writer 방지, CR/PVC 보존 |
| 후속 HA | 리더 중단/Lease 만료/API 단절 중 중복 자식·allocation·reclaim 없음 |

기존 `tests/integration/review_smoke.py`는 control-plane namespace와 최소 2개 workload
namespace를 별도 입력으로 받도록 변경한다. fake API 저장소도 `(kind, namespace, name)`으로
만들고 metadata.namespace가 없는 현재 fixture를 보완한다. 실제 API 서버를 사용하는 CPU
통합 검증을 CI에 추가하고, GPU 시험은 별도 환경에서 실행한다.

현행 52개 CPU 테스트와 `scripts/check-repository.py`는 분석 시 통과했다. 이 결과는 기존
기능의 기준선이며 중앙 관리 기능 검증을 뜻하지 않는다. CRD server validation, Helm render/lint,
실제 `kubectl auth can-i`, docs strict build, CPU 통합 및 GPU 수명 주기 시험을 릴리스 조건으로 한다.

## 현재 실험 환경 이전 계획

namespace를 새 이름으로 옮기거나 모든 실험 VM을 재생성할 필요는 없다. 제어기만 중앙으로
이전하고 기존 namespace/UID/PVC를 유지하는 방식으로 시작한다.

1. 현재 release values/manifests, CR 상태·UID, webhook, RBAC, PVC/PV 경로와 정책을 보존한다.
   민감한 TLS/인증 자료는 공개 저장소에 기록하지 않는다.
2. 별도 테스트 환경에서 중앙 배포와 두 namespace 검증을 완료한다.
3. 새 중앙 release를 기존 관리 범위와 겹치지 않는 시험 namespace에 설치한다.
4. 이전 대상의 새 요청을 중단하고 기존 allocation을 회수한다. 초기 이전은 실행 중
   allocation의 무중단 인계를 지원한다고 가정하지 않는다.
5. 대상의 기존 controller만 정지하고 Pod 종료를 확인한다. 기존 webhook은 유지한다.
6. 중앙 webhook의 대상 접근권한·TLS·검증을 준비한다. 이전 시에만 신뢰하는 controller SA
   목록에 기존/중앙 신원을 명시한다. old webhook이 중앙 SA를 거부할 수 있으므로 필요하면
   구 webhook을 호환 버전으로 먼저 갱신한다. 단순히 두 webhook을 겹치면 된다고 가정하지 않는다.
7. 중앙 webhook을 활성화하고 정상 검증을 확인한 뒤 구 webhook 등록을 제거한다.
   중앙 controller의 대상 namespace 처리는 admission 전환 후에 연다.
8. 중앙 관리와 회수 검증 후 구 release를 제거한다. CRD/CR/PVC를 보존하고 공유 리소스
   소유권을 확인한다. 정상 동작을 확인한 뒤 임시 SA 신뢰도 제거한다.
9. 실패 시 중앙 처리를 먼저 중지하고, 구 webhook 및 controller 신원을 복구한 뒤
   구 controller를 재개한다. 데이터 경로와 UID를 유지하며 양쪽 writer를 동시에 켜지 않는다.

| 기존 namespace | 이전 판단 |
|---|---|
| `flyt-evidence` | 첫 실제 관리 대상 후보. CR/PVC/증거 유지, 기존 controller/webhook만 중앙으로 대체 |
| `flyt-gpu-validation` | `shm-channel-a`의 `Draining / AwaitingDetachEvidence` 해결 전 이전·삭제 보류 |
| `flyt-review-validation` | 새 review 통합 시험으로 대체 가능한지 확인 후 기존 release 정리 |
| `flyt-infra-validation` | 실행 중 `basic-vm` 보존. 자동 관리 편입하지 않음 |
| `flyt-evidence-baseline`, `flyt-overhead-tcp` | SHM 중앙 관리의 필수 대상이 아님. 실험 보존/삭제는 별도 판단 |

namespace 수가 반드시 하나로 줄어드는 작업은 아니다. **컨트롤러 설치가 하나로 통합되고,
사용자·실험 workload namespace는 독립적으로 남는 것**이 완료 상태다.
