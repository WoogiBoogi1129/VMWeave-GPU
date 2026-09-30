# VMWeave Go Operator·중앙 관리·API 명칭 전환 최종 계획

작성: 2026-09-30. 분석 기준: `c3c07c9`. **상태: 구현 전 계획**.
이 문서가 이전 중앙 제어기 계획을 대체한다. 코드/차트/클러스터는 아직 변경하지 않았다.

## 1. 최종 결정

1. Go + Operator SDK/controller-runtime으로 중앙 Controller와 Webhook을 구현한다.
2. `vmweave-system`의 release 하나가 여러 사용자 namespace를 관리한다.
3. 새 Kubernetes API에서 `Flyt*` Kind, `flyt.dev` group, `flyt*` resource 이름을 제거한다.
4. VM·VMI·virt-launcher·GPU 요청·Channel·Worker·PVC는 사용자 namespace에 유지한다.
5. 설치 docs는 관리자 중앙 설치와 사용자 VM 사용 절차로 정형화한다.
6. 기존 실험 증거·디스크를 보존하며 중단·회수를 수반하는 API 이전을 제공한다.

Python 중앙화를 먼저 완성하는 중간 단계는 생략한다. 기존 Python은 동작 비교와 구API 회수에
사용하고, 신규 Go Operator는 신API를 관리한다. 언어 자체보다 Reconcile·권한·상태·회수의
계약을 표준화하는 것이 핵심이다.

```text
vmweave-system
  vmweave-controller (Go, leader election)
  vmweave-webhook    (Go, TLS)
  ServiceAccounts / Service / TLS Secret / Lease
         ├── team-a: GPUProfile / GPURequest / SharedMemoryChannel
         │          ChannelAttachment / VM / VMI / virt-launcher / Worker / PVC
         └── team-b: 같은 구성, 동명 객체도 독립 처리
```

Controller/Webhook은 동일 Go 코드베이스·이미지의 별도 실행 모드와 Deployment로 구성하고
서로 다른 SA/RBAC를 사용한다. namespace가 늘어도 두 Deployment를 추가하지 않는다.
KubeVirt/HAMi의 설치 위치는 유지한다. 사용자 namespace와 VM/PVC를 중앙 release의 소유로 만들지 않는다.

## 2. 새 API와 명명 규칙

새 Kind는 제품 접두사를 반복하지 않고 아래 명칭으로 정한다. 네 리소스 모두 Namespaced,
초기 version은 `v1alpha1`이다. **API group 제안은 `vmweave.io`이며 도메인 관리 권한은 미확인이다.**
최초 배포 전에 프로젝트가 관리하는 DNS 이름을 확인해 group을 확정한다. 아래 이름은
`vmweave.io`가 확정될 경우의 설계안이며, 확인 없이 도메인 소유를 전제로 릴리스하지 않는다.

| 기존 Kind / CRD | 새 Kind | 새 CRD 이름(제안 group 기준) |
|---|---|---|
| `FlytGPUProfile` / `flytgpuprofiles.flyt.dev` | `GPUProfile` | `gpuprofiles.vmweave.io` |
| `FlytGPURequest` / `flytgpurequests.flyt.dev` | `GPURequest` | `gpurequests.vmweave.io` |
| `FlytSharedMemoryChannel` / `flytsharedmemorychannels.flyt.dev` | `SharedMemoryChannel` | `sharedmemorychannels.vmweave.io` |
| `FlytChannelAttachment` / `flytchannelattachments.flyt.dev` | `ChannelAttachment` | `channelattachments.vmweave.io` |

singular/listKind도 대응하는 명칭으로 생성한다. `fgp`/`fgr`는 이관하지 않고 초판은 shortName을
필수로 두지 않는다. 예제와 이전 도구에서는 group을 포함한 resource 이름으로 구API와 구분한다.

| 대상 | 신규 기준 |
|---|---|
| system namespace / release | `vmweave-system` / `vmweave` |
| chart / Operator image | `vmweave-operator` |
| annotation / label / finalizer | 확정한 새API 도메인; 예: `vmweave.io/shm-detach` |
| Operator env / metrics | `VMWEAVE_*` / `vmweave_*` |
| 신규 runtime image | `vmweave-worker`, `vmweave-hook` 등, digest 고정 |
| 사용자 namespace 예제 | `team-a`, `team-b` |

현행 공개API와 신규 배포 인터페이스에서 flyt를 제거한다. LICENSE/NOTICE/출처, `legacy/**`,
과거 결과, 호환 adapter, C의 기존 ABI 이름은 일괄 치환하지 않는다. 잔존 허용 목록과 이유를
기록한다. 실험 원본의 UID·명칭·해시는 보존한다. 기존 namespace 자체의 rename/recreate는 제외한다.

## 3. Go 이식 범위와 코드 구조

| 현재 구현 | 변경 |
|---|---|
| `control_plane.py`, `channel_controller.py` | Go Channel Reconciler와 상태 전이 로직 |
| `kube.py`, `settings.py`, `health.py` | controller-runtime/client-go, 설정·health·metrics |
| `admission.py` | Go AdmissionReview handler/validator |
| `observe.py` | Go detach 관측 로직과 Worker 보고 client |
| `supervisor.py` | 첫 release는 신API adapter로 호환, 후속 Go 바이너리로 이전 |
| `provision.py`, `reclaim.py`, `domain_hook.py` | 초기 호환 유지, 후속 Go helper로 이전·검증 |
| C/CUDA Guest·Worker·queue·dispatcher | 유지; ABI/알고리즘 변경 제외 |
| Python 실험·분석·문서 도구 | 유지; 현재 사용 경로의 API/namespace 입력 갱신 |

```text
operator/
  PROJECT / go.mod / go.sum
  cmd/main.go
  api/v1alpha1/             API 타입과 validation markers
  internal/controller/     Reconcile, dependency event mapping
  internal/admission/      Channel/Attachment/VMI/migration 검증
  internal/lifecycle/      상태 전이와 detach 계약
  internal/scope/          관리 namespace 설정
  config/crd/bases/         생성 CRD
  config/rbac/              권한 정의
  tests/                   envtest와 계약 시험
charts/vmweave-operator/
deploy/examples/vmweave/
```

Go/SDK/controller-runtime/client-go/KubeVirt API 버전을 고정하고 실험 노드 Kubernetes v1.37과
호환성을 시험한다. SDK 생성 기본값을 그대로 검증 완료로 간주하지 않는다.
Go 타입·markers를 신CRD의 원본으로 두고 chart 사본은 생성 및 차이 검사로 관리한다.
구CRD 사본은 호환용으로 동결하고 신CRD와 동일해야 한다는 기존 검사를 분리한다.
OLM은 초기 필수 의존성이 아니다. Helm으로 배포하며 사용자에게 Go/SDK 설치를 요구하지 않는다.

## 4. 중앙 Reconcile·권한·Webhook

- 설치 위치와 `management.namespaces`를 분리한다. 초기에는 명시 목록을 쓰고 빈 목록은 거부한다.
  controller cache, RoleBinding, webhook selector의 대상 목록은 같은 설정에서 생성한다.
- 중앙 SA에 사용자 namespace별 RoleBinding을 부여한다. 이 권한에 맞춰 namespace별 list/watch를
  사용하며 cluster-wide list가 가능하다고 가정하지 않는다. 불필요한 Secrets/wildcard/bind/escalate
  권한은 부여하지 않는다. Node/PV 조회 등 필요한 cluster 권한은 별도로 한정한다.
- reconcile/cache key는 NamespacedName이며 UID/generation/RV 검증을 유지한다.
  VM/Request/Profile/PVC/Channel/Attachment 참조는 같은 namespace로 한정한다.
- 주 reconciler는 Channel이다. 모든 CRD에 형식적으로 독립 controller를 생성하지 않는다.
  Pod/Attachment owner watch와 VM/VMI/PVC/Request/Profile index를 통해 관련 Channel을 enqueue한다.
  누락된 참조의 등장·삭제·주기적 재검사도 처리한다.
- 짧고 멱등한 단계로 나누고 sleep 대신 requeue를 사용한다. 한 객체/namespace의 실패가
  다른 namespace의 전체 재시도를 늦추지 않게 한다. 변동 없는 status/Events 쓰기는 억제한다.
- cache가 최신이라는 가정을 하지 않는다. admission과 파괴적 회수 결정에 필요한 직접
  API 조회, UID/RV 충돌 처리, 재시도를 명시한다.
- 표준 Lease leader election을 처음부터 포함하되 기본 replica는1로 둔다. 복수 replica는
  리더 상실·API 단절 시험 후 지원하며, Lease만으로 SHM 외부 부작용이 fence된다고 보지 않는다.
- Worker/prepare/reclaim/SA/Role은 현지에 생성한다. central controller를 cross-namespace
  ownerReference로 연결하지 않는다. Profile은 현지에 유지하고 승인자와 사용자 권한을 나눈다.
- Webhook은 AdmissionReview namespace로 조회하고 object namespace와 대조한다. 중앙 controller SA와
  현지 Worker SA+Pod UID를 구분하며, 다른 namespace의 동명 SA 보고를 거부한다.
- 일반 VM은 허용한다. 관리 여부를 annotation 하나만으로 판단하지 않고 이전/새 binding,
  owner VM UID, Channel 참조를 확인해 annotation 제거로 검증을 우회하지 못하게 한다.
- 관리 VM의 binding 불변성·배치·hook/PVC·migration 제한을 유지한다. 관리 namespace 범위에서만
  webhook을 적용한다. 일반 VM의 서버 내부 허용만으로 webhook 장애 영향까지 사라지는 것은 아니다.
- review는 workload 쓰기 권한 없이 검증하며, 동일 대상에 review/active controller를 겹치지 않는다.
- namespace/name/UID 로그, 처리 지연·API 오류·drain 대기 관측을 제공하고 UID metric label은 피한다.

## 5. Helper 호환·회수

신API와 기존 Python helper는 자동 호환되지 않는다. Worker 보고 API/group/kind, Worker RBAC,
hook annotation, controller SA 인증을 맞춘 신규 helper image가 필요하다. 명시 설정으로
구API/신API를 선택하고 암묵적 fallback은 금지한다. 설정이 충돌하면 거부한다.
새 Operator가 만드는 env/command/mount는 image capability와 검사하며 기존 실행 image는 교체하지 않는다.

후속 Go helper 전환은 별도 계약 시험을 통과해야 한다:

- supervisor의 signal/process group/child reap 및 slot 재시작 금지.
- provision의 layout/endianness/offset/권한/크기와 기존 C reader의 호환.
- reclaim의 allocation/세대 확인, symlink 거부, dirfd·O_NOFOLLOW 상당 보장, fsync/삭제 순서.
- hook XML·PCI slot·QEMU 인자·KubeVirt sidecar-shim 호환.

Pod/VMI 누락을 detach 증거로 처리하지 않는다. UID·세대·terminal 증거를 내구성 있게 저장한 후
finalizer를 해제한다. 정상 해제는 **신규 접수 차단 → drain → detach → reclaim → finalizer 해소 →
관리 범위 해제 → webhook/RBAC 해제 → namespace 삭제** 순서다.
Terminating namespace에는 reclaim Pod를 신규 생성할 수 있으리라고 가정하지 않는다.
초판은 namespace 직접 DELETE의 자동 회수를 보장하지 않으며 그 상태를 Condition으로 보고하고
증거를 보존한다. 강제 finalizer 제거를 정상 해결책으로 삼지 않는다.

## 6. API 이전: 단순 rename이 아닌 신규 객체 생성

group/kind/plural 변경은 다른 API로의 이전이다. conversion webhook은 같은 CRD 안의 version
변환이므로 이를 대신하지 못한다. 신CR은 새UID를 가지며, 옛 UID/RV/status/ownerReferences를
복사해서는 안 된다. [CRD versioning](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definition-versioning/).

초기 이행은 정지·회수 후 신규 할당이며, 실행 중 allocation 무중단 인계는 제외한다.
한 VM/PVC를 구API와 신API controller가 동시에 관리하지 않는다.

1. inventory: 구CRD/CR, VM annotation, PVC/PV, RBAC/webhook/release/image digest를 보존한다.
   민감한 TLS/인증 자료는 공개하지 않는다.
2. dry-run: 재사용 VM/PVC, 재생성 Profile/Request/Channel, 보관만 할 Released/Attachment 이력,
   미해결 Draining 대상을 분류한다. 과거 완료 Channel을 전부 재생성하여 실행시키지 않는다.
3. 구controller에서 신규 요청을 멈추고 VM을 Halted로 만든 뒤 정상 회수를 완료한다.
   미해결 대상은 제외한다. namespace 안의 모든 구allocation이 안전해지기 전 controller를 내리지 않는다.
4. 신API/Go Operator는 별도 시험 namespace에서 먼저 검증한다. 이전 대상의 write scope는 아직 열지 않는다.
5. 구controller 종료를 확인한다. 구API/webhook/증거는 구Channel 최종화와 복구에 필요한 동안 유지한다.
6. UID 확인된 Halted VM에만 구binding annotation/hook 설정을 해제한다. 구webhook이 새controller를
   거부하는 문제를 호환 업데이트 또는 검증된 scope 전환으로 해결한다. 맹목적 webhook 중복이나
   무조건적인 검증 해제로 이전하지 않는다.
7. VM/PVC UID는 유지한다. 새Profile 생성→새UID 조회→새Request의 profileRef 구성→새Request UID로
   새Channel 생성 순서로 참조를 다시 연결한다.
8. 구Attachment, allocation/generation/session/status는 이관하지 않는다. 새실행의 할당·Attachment는
   새controller가 새증거로 생성한다. 기존 child ownerReferences/finalizer를 신CR로 강제 덮어쓰지 않는다.
9. 구→신 `(group,kind,namespace,name,uid)` 매핑과 checkpoint를 저장한다. 재실행 시 UID/spec를
   대조하고 동일 이름의 외부 객체를 덮어쓰지 않는다.
10. scope를 열고 GPU 실행·quota·회수·일반 VM 공존을 검증한다. 구상태는 역사 자료로 보존한다.
11. 구CR/worker/webhook/RBAC/도구 참조가 없고 필요한 자료가 보존되었는지 확인한 뒤 구API를
    별도 폐기한다. CRD 삭제는 그 CR도 삭제하므로 정상 설치/upgrade/uninstall에 포함하지 않는다.
    [CRD 삭제 동작](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/).

rollback은 checkpoint별로 정의한다. 신allocation 시작 전에는 신scope를 멈추고 구설정을 복구한다.
시작 후에는 신측 정상 회수 후 VM/PVC로 구API의 새요청·새Channel을 생성해야 한다.
구Released Channel/status를 되살리지 않는다. 회수 증명이 없으면 구측을 재개하여 같은 자원을 쓰지 않는다.

기존 환경에서는 `flyt-evidence`가 이전 후보이며, `flyt-gpu-validation/shm-channel-a`의 미해결
Draining은 별도 차단 조건이다. `flyt-infra-validation/basic-vm`은 보존하고 자동 편입하지 않는다.
모두 앞선 조회 시점의 상태이므로 실제 이행 전에 다시 inventory한다. 구namespace 이름 보존과
신규 제품 API에서 flyt 제거는 서로 다른 범위다.

## 7. docs와 표준 설치

| 문서 | 정형화할 역할 |
|---|---|
| `getting-started/index.md` | 관리자 설치/사용자 VM 배포 단일 입구 |
| `prerequisites.md` (신규) | 검증 버전, KubeVirt/HAMi/GPU, local PV, image 사전 준비 |
| `install.md` (신규) | 중앙 Operator 한 번 설치, CRD/RBAC/TLS/readiness |
| `namespaces.md` (신규) | 등록/확인/drain/해제, Controller 재설치 없음 |
| `first-vm.md` (신규) | 신API의 Profile/PVC/VM/Request/Channel, 시작·실행·회수 |
| `cpu-control-plane.md` | 같은 Go Operator의 review 개발 검증; active 전 별도 release 불필요 |
| `gpu.md` | GPU/Guest 준비, 공통 설치 안내 참조 |
| `reference/configuration.md`, API 참조 | 신group/kind/scope/UID/env/values/상태 |
| `guides/operations.md` | system 로그와 사용자 CR/Worker 조회 구분 |
| `upgrade-uninstall.md` (신규) | CRD 갱신, TLS, 회수, 데이터 보존, release 제거 |
| `migrate-to-vmweave-api.md` (신규) | 구flyt API 이전, dry-run/checkpoint/rollback |
| README/architecture/roadmap/MkDocs nav | 중앙 Go Operator와 새로운 입구 반영 |

모든 절차는 목적·담당자→전제→입력→실행→예상 결과→실패 조치→보존/삭제 대상을 명시한다.
`CONTROL_PLANE_NAMESPACE`, `WORKLOAD_NAMESPACE`, `RELEASE_NAME`을 구분한다.
사용자 절차에 CRD/ClusterRole/Controller 설치를 넣지 않는다. uid는 생성 후 조회하는 도구로
연결하고 과거 실험 UID/IP/UUID/path를 복사하도록 하지 않는다.

공식 경로는 새Helm chart와 설치 보조도구다. CRD 검증/적용→RBAC/TLS→Deployment 준비→webhook
등록을 조율하며 raw Helm/실험 renderer/OLM을 동등한 기본 경로로 나열하지 않는다.
관리 대상 추가는 RBAC→webhook→controller 접수, 해제는 회수 완료 후 반대 순서로 한다.
Helm upgrade가 모든 변경을 원자적으로 적용한다고 가정하지 않는다.
control-plane/workload imagePullSecret은 namespace별로 준비한다. cert-manager 경로도 실제 검증한다.
구실험 docs/결과는 보존하고, 새구현·예제 검증이 끝나는 release에서 실제 설치 docs를 전환한다.

## 8. 실행 단계와 완료 조건

| 단계 | 결과물 | 완료 기준 |
|---|---|---|
| A. 계약 고정 | API domain 확인, schema/명명 대응, 기존 동작fixture, 의존버전표 | 기존 제약/상태의 신API 처리 방식 결정 |
| B. Go read-only | SDK 구조, 타입/CRD, cache/queue/Lease/metrics, review | 2namespace 동명CR 독립 처리, workload 쓰기 없음 |
| C. Active/Admission | lifecycle, Worker, detach/reclaim, 일반 VM 판정, 인증 | 실API+GPU에서 기존 안전 조건 충족 |
| D. 배포와 helper | chart/TLS/RBAC, 호환 helper image, 등록/해제CLI | 신규 환경 중앙1release 실행·회수 |
| E. 이전 도구 | inventory/dry-run/apply/checkpoint/rollback | UID 참조 재구성, 이중 관리 없음, 중단 재개/복구 |
| F. 초기 release | 표준 docs/예제/CI/증거 | docs만으로 2namespace 실행·회수·해제 재현 |
| G. 기존 환경 이전 | namespace별 이행 및 구API 폐기 판단 기록 | 데이터·증거 보존, 불필요한 구controller 해소 |
| H. Go helper | supervisor/provision/reclaim/hook 바이너리 | ABI/signal/XML/파일 안전성 호환 검증 |

A~F가 초기 중앙 Go Operator 릴리스다. H 전까지 production helper에 Python이 남는다고 명시한다.
C/CUDA와 Python 분석도구는 Go화 완료의 조건에서 제외한다. HA 복수replica는 별도 장애 검증 후 켠다.

필수 검증:

- Go unit/계약: 상태 전이, RV 충돌, Released 삭제, 누락과 detach 증거 구분.
- envtest: CEL/default/status, namespace 격리, SA 인증, binding 삭제 우회, 동일 이름 재생성.
- 실cluster: KubeVirt·GC·namespace termination·RBAC·TLS·리더 상실. envtest를 실제 kubelet/GC/GPU의
  대체 검증으로 취급하지 않는다.
- GPU: 다중namespace 동시 실행·quota·실제 mapping·drain/reclaim·restart.
- 이전: UID 매핑·구owner/finalizer/annotation·helper호환·중단재개·rollback.
- 배포: Go test/vet, generated schema 비교, Helm lint/render, API server validation, docs strict build.
- 명명: 현행 공개manifest/API/표준예제에서 flyt 제거; 호환/출처/구ABI/이력은 허용 목록 검사.
- 기존 CPU 52건은 기준선이며 동일 테스트 개수를 새구현 정확성의 증명으로 삼지 않는다.

최종 수용 조건은 **system의 중앙 Go Controller/Webhook이 새API로 서로 다른 사용자 namespace의
동명 VM 관련CR을 관리하고, 일반 VM을 방해하지 않으며, 할당·회수·관리해제까지 표준docs로
재현되는 것**이다. 구API 제거는 데이터 보존을 확인하는 별도 운영 단계다.

## 참고

- [Operator SDK](https://sdk.operatorframework.io/docs/overview/)
- [Manager scope](https://book.kubebuilder.io/reference/manager-scope.html)
- [Envtest](https://book.kubebuilder.io/reference/envtest.html)
- [이전 중앙화 검토안](central-controller-plan.md): Python/API 유지 결정은 본문으로 대체됨.
