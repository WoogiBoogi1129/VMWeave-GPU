# VM 내부 다중 GPU Pod 지원 개발 계획

작성일: 2026-11-13 (Asia/Seoul). 상태: 0절의 단순화 범위로 후보 구현 및 실제 VM/GPU 검증 완료.
분석 기준: `7fa6ac673640045ab95c29ea085dd0b7c3ee81ff` 및 현재 작업 트리.
사용자가 확정한 목표는 **VM 내부 Kubernetes에서 여러 GPU Pod 실행**이다.
초기 계획 이후 사용자가 구현·검증을 승인하여 독립 시험 VM과 내부 Kubernetes를 구성했다.
구현과 실험 결과는 [고정 슬롯 검증](../../experiments/fixed-slots/README.md)에 기록한다.
아래 1절 이후는 최초 확장 계획의 분석 기록이다. **이번 구현 범위는 0절이 우선**하며,
N=4, Pod별 quota, 통합 세션 관리·metrics는 포함하지 않는다.

**0. 고정 슬롯 기준 단순화 검토 — 다음 구현의 권장 범위**

2026-11-13 후속 검토. 슬롯 개수를 고정하는 방향을 반영해 다음 구현을 **고정 2슬롯의 A 수준**으로
줄이는 안을 권장한다. 아래 1~10절은 전체 개발 로드맵이며, 다음 구현에서는 이 절의 범위를 우선한다.
Pod별 VRAM/compute 격리라는 후속 목표를 달성한 것으로 처리하지 않는다.

| 기존 계획의 요소 | 단순화안 | 코드 근거·남는 조건 |
|---|---|---|
| 새 슬롯 설정 API·CRD 변경 | 기존 `spec.sessions` 사용. 검증 대상은 1/2슬롯 | 현재 CRD는 이미 sessions 변경을 금지하므로 새 불변성 정책 불필요. 승인 Profile과 runtime 호환 검사는 유지 |
| 새 Guest supervisor 데몬 | 기존 `guest_bootstrap.py`에 최소 child 실행·대기·종료 처리 추가 | 기존 Broker가 `--socket`, `--status`, `VMWEAVE_SLOT`을 이미 지원. 부팅 layout은 한 번만 준비 |
| 통합 discovery v2·상태 집계기 | Broker마다 상태 파일 하나, Plugin이 슬롯별 직접 읽기 | 기존 Publisher/Check의 검증 재사용. 슬롯 번호·session ID·슬롯 수의 명시적 연결 검증은 추가 |
| Host Worker·CUDA 프로토콜 개편 | 기존 슬롯별 supervisor/session worker/SHM layout 재사용 | 이미 N슬롯 프로세스와 슬롯당 fresh epoch/child가 있음. 실제 2슬롯 동작과 부분 장애는 시험 필요 |
| 별도 Pod→세션 예약 관리자 | 기존 kubelet 예약과 Broker 단일 접속 lock 활용 | Plugin Allocate에서 새 lease/세션을 만들지 않음. Plugin은 노드당 하나 유지 |
| VM 생성·내부 Kubernetes 설치 통합 자동화 | 기존 설치 절차와 manifest를 사용해 재현 확인 | 새 orchestration CLI는 동시 실행 검증 후 진행. VM 준비 자체는 생략하지 않음 |
| Pod별 quota·DRA·compute 정책 | 첫 구현에서 제외, 기존 VM 전체 quota 공유 | 각 Pod의 VRAM 보장·공정성·메모리 초과 영향 격리는 제공하지 않음 |
| 자동 장애 복구·통합 metrics | 기존 로그·상태 파일·새 실행 증거로 검증 | 고장 슬롯은 Unhealthy로 두고 재기동하지 않음. 정상 Pod 종료 후 슬롯 재사용은 필수 |

고정값은 소스 여러 곳에 숫자 2를 하드코딩한다는 뜻이 아니다. 관리자가 Channel에서 지정한 개수를
부팅 layout이 전달하며, Guest는 이를 한 번 읽어 사용한다. Plugin 설정에 기대 개수를 넣는 경우에도
Broker가 layout에서 읽은 승인 개수와 일치해야만 광고한다. 파일 개수나 chart 값만으로 존재하지 않는 슬롯을 만들지 않는다.
현재 CRD에서 sessions가 immutable이므로 개수 변경은 단순 VM 재부팅이 아닌
기존 binding 회수와 Channel 재생성 절차가 필요하다.

권장 파일 배치는 슬롯별로 고정한다.

```text
/run/vmweave/slots/0/gpu.sock
/run/vmweave/slots/1/gpu.sock
/run/vmweave-device-plugin/slots/0/status.json
/run/vmweave-device-plugin/slots/1/status.json
```

상태 JSON은 기존 readiness·timestamp·allocation/generation·boot/hash 검증을 재사용한다.
여기에 `slotIndex`, `sessionID`, `slotCount`를 더해 파일 경로와 실제 layout 슬롯의 연결을 확인한다.
이것은 검증 필드의 소규모 확장이며 새 중앙 세션 관리자나 통합 `slots[]` 게시기를 뜻하지 않는다.
버전 식별은 유지하고 다중 슬롯 레코드는 새 계약으로 검증한다. 1슬롯의 기존 경로/계약은 유지하며,
2슬롯 모드에서는 구 Plugin용 root status/socket을 게시하지 않아 잘못된 호환 경로를 만들지 않는다.

Guest 부팅 코드는 child마다 별도의 환경변수를 전달하고 `exec` 경계를 통해 독립 Broker를 실행한다.
프로세스 전체 환경을 바꾸며 thread별로 슬롯을 공유시키지 않는다. 자식 종료를 회수하고,
서비스 종료 시 모든 자식을 정리하며, 한 Broker 장애로 다른 Broker까지 종료시키지 않는 처리는 필요하다.
새 장기 실행 관리 서비스는 줄일 수 있지만 이 최소 프로세스 수명 주기 코드는 제거할 수 없다.

다음 네 가지는 유지한다: **중복 접속 차단, 새 연결의 epoch, 종료 후 CUDA child 회수,
고장 슬롯 신규 할당 차단**. 소비된 SHM ring 재시작 금지와 Pod별 소켓 directory 한정 mount도 유지한다.
고정 슬롯은 상태가 없는 슬롯을 뜻하지 않으며, 상태를 별도 CRD/DB에 복제하지 않는 것으로 단순화한다.

최소 변경 묶음은 (1) Operator admission, (2) Guest bootstrap/상태 게시와 필요한 패키징,
(3) Device Plugin의 슬롯별 검사·광고·mount, (4) 해당 회귀·E2E 검사다.
CUDA C 코드·SHM ABI·새 CRD는 우선 변경하지 않고, 기존 구조로 불가능함을 보여주는 실패가 있을 때 재검토한다.

필수 검증은 1슬롯 회귀, 2개 Pod의 겹친 CUDA 실행과 정답, 세 번째 Pod의 대기,
한 Pod 종료 후 재사용, 다른 슬롯 접근 거부, 한 Broker 장애 때 나머지 작업 지속이다.
상태 파일 누락·슬롯 불일치·이전 generation 및 Plugin 재등록도 CPU 검사에 포함한다.
실제 구현·GPU 검증의 통과 여부와 한계는 위 실험 기록을 기준으로 판단한다.

**1. 결론과 목표**

VM 생성과 단일 GPU Pod 실행 기반은 이미 있다. 새 가상화 시스템을 만드는 대신,
기존 VM lifecycle과 SHM의 여러 슬롯을 Guest Broker·Device Plugin까지 연결하는 것이 우선이다.
권장 경로는 **VM 1대 → Channel 1개 → 독립 SHM 슬롯 N개 → 슬롯별 Broker/Worker 세션 → Pod N개**다.
최초 N=2, 다음 N=4로 검증하고, 현재 wire/layout 상한 32를 제품 지원 수치로 간주하지 않는다.

완료 수준을 구분한다.

| 수준 | 사용자에게 제공하는 기능 | 완료 조건 |
|---|---|---|
| A: 동시 실행 | VM GPU quota를 공유하는 여러 Pod의 슬롯 예약과 독립 CUDA 세션 | 두 Pod가 실제로 겹쳐 실행, 정답·회수·오류 격리 검증 |
| B: Pod별 메모리 배분 | 슬롯마다 정해진 VRAM 예산, 초과한 Pod만 OOM | 지원 메모리 경로의 한도 집행 및 합계·내부 메모리 검증 |
| C: Pod별 compute 정책 | 상대 가중치 또는 연산 상한 정책 | 구현 방식과 실제 공정성·상한 시험을 별도 통과 |

요청의 첫 개발 릴리스 목표는 A+B다. A만 통과한 중간 결과는 “VM quota 공동 사용”으로 표시한다.
GPU 예약, CUDA 실행, 메모리 격리, 연산 성능 보장은 서로 다른 기능이다.
여러 프로세스의 CUDA 실행 시간이 겹친다고 GPU 커널의 하드웨어 병렬 실행까지 입증되는 것은 아니다.

**2. 현재 구현과 정확한 차단 지점**

| 영역 | 현재 코드에서 확인한 동작 | 보완해야 할 점 |
|---|---|---|
| VM 준비 | [사용자 예제](../../deploy/examples/vmweave/user.yaml)는 Halted VM/PVC. [생성 스크립트](../../scripts/operator/create-channel.py)는 기존 VM/PVC/Profile UID를 읽어 Request/Channel 생성 | 영구 root disk·Guest package·내부 Kubernetes 설치를 묶는 반복 가능한 준비 도구 |
| VM lifecycle | [admission.go](../../operator/internal/engine/admission.go)의 `Validate()`가 `lifecycle: VM`에서 `sessions != 1` 거부 | 승인 Profile 범위의 N슬롯 허용, 기존 1슬롯 기본값 유지 |
| SHM 구조 | [provision.py](../../runtime/shm/control/provision.py)의 `make_layout()`은 1~32개 독립 ring/payload 영역을 생성 | layout 재사용, N슬롯의 크기·동일성 검사 추가 |
| 부팅 layout | [persistent.go](../../operator/internal/engine/persistent.go)의 `installBootLayout()`도 복수 session ID를 직렬화 | Python/Go layout 생성의 바이트 일치 회귀 검사 |
| Guest 부팅 | [guest_bootstrap.py](../../runtime/shm/control/guest_bootstrap.py)는 슬롯 0만 허용하고 Broker 하나 실행 | 슬롯별 Broker 프로세스 실행·상태 수집 |
| Broker | [guest_broker.py](../../runtime/shm/control/guest_broker.py)의 `serve()`는 비차단 lock, owner 모드는 `busy` lock/대기 큐 1개 | 단일 Broker의 lock 제거 대신 독립 슬롯별 Broker 유지 |
| transport owner | [owner.c](../../runtime/shm/src/owner.c)는 생성 PID/thread를 검사하며 슬롯 하나 소유 | 슬롯당 owner 유지; 여러 thread에서 같은 owner 호출 금지 |
| Host Worker | [supervisor.py](../../runtime/shm/control/supervisor.py)는 이미 슬롯별 실행 파일 생성 | persistent N슬롯 통합 검증, 부분 장애 상태·자원 예산 보강 |
| CUDA 세션 | [worker_sessions.c](../../runtime/shm/src/worker_sessions.c)는 슬롯별 active epoch 1개와 CUDA child 1개 유지 | 슬롯별 quota 전달·사용량·회수 관측 추가 |
| discovery | [guest_status.py](../../runtime/shm/control/guest_status.py)는 layout 1슬롯만 허용, `maxClients: 1` 게시 | 슬롯별 상태를 담는 버전 2 계약 |
| Device Plugin | [plugin.go](../../integrations/kubernetes-device-plugin/internal/plugin/plugin.go)는 `vmweave-slot-0` 하나만 광고. `Check()`는 `MaxClients == 1`, `Allocate()`는 컨테이너 요청 1개만 허용 | 슬롯 목록·개별 health·컨테이너별 선택 슬롯 mount 지원 |
| 외부 GPU quota | [worker.go](../../operator/internal/engine/worker.go)는 Worker Pod 하나에 VM 전체 gpumem/gpucores 또는 DRA claim 설정 | 내부 Pod마다 별도 quota가 생기는 것은 아님. 슬롯별 집행 계층 필요 |
| 런타임 guard | [runtime.c](../../runtime/shm/cuda-dispatch/src/runtime.c)의 `worker_guard()`는 HAMi library, GPU UUID, VM 메모리 한도 검사 | VM 한도와 슬롯 한도를 분리해 관리 |

따라서 `replicas` 또는 `--sessions`만 늘리는 것으로 해결되지 않는다.
Plugin의 광고 수만 늘리면 동일 socket으로 연결되어 busy 오류를 받으며,
Broker lock만 없애면 단일 owner/thread 및 active epoch 계약을 깨뜨린다.

기존 [내부 Kubernetes 실험](../../experiments/nested-k8s-gpu/README.md)은 Pod GPU 실행 기반이고,
[현재 Plugin](../guides/kubernetes-device-plugin.md)은 단일 슬롯 예약 기반이다.
두 자료를 새 다중 슬롯·동시 실행·Pod별 quota의 검증 결과로 인용하지 않는다.

**3. 권장 구조와 선택 이유**

```text
외부 Kubernetes / 같은 GPU 노드
  GPUProfile + GPURequest: VM 전체 VRAM/compute 예산 예약
  SharedMemoryChannel: lifecycle=VM, sessions=N
  ├─ KubeVirt VM: 영구 root disk + 내부 Kubernetes
  │    ├─ Guest broker supervisor [신규]
  │    │    ├─ slot 0 broker ─ socket /run/vmweave/slots/0/gpu.sock
  │    │    └─ slot 1 broker ─ socket /run/vmweave/slots/1/gpu.sock
  │    ├─ Device Plugin: 슬롯 0, 1 광고
  │    ├─ Pod A: slot 0 directory만 mount
  │    └─ Pod B: slot 1 directory만 mount
  └─ Host Worker Pod: VM 전체 GPU quota
       ├─ slot 0 transport worker → CUDA child A
       └─ slot 1 transport worker → CUDA child B
             ↓ 동일 물리 GPU, 외부 HAMi 또는 HAMi DRA 할당
```

각 슬롯은 기존 request/response ring, payload arena, owner thread, session epoch를 독립적으로 사용한다.
CUDA 프로세스가 끝나도 transport owner는 유지하고 다음 연결에 새 epoch/child를 만든다.
한 VM에 Channel 여러 개를 붙이거나, 하나의 ring에서 임의 다중 session을 multiplex하는 방식은
초기 변경 범위에서 제외한다. 기존 다중 슬롯 구조를 쓰면 wire 변경과 response demultiplexing을 줄일 수 있다.

VM 여러 대에 Pod 하나씩 배치하는 방법은 기존 단일 슬롯 경로를 활용하는 임시 대안이지만,
VM 한 대에서 여러 Pod를 실행하는 이번 목표의 완료 조건으로 삼지 않는다.

**4. 사용자 API와 자원 의미**

외부 관리자는 `GPUProfile.maxClients`와 VM 전체 예산을 승인한다.
VM 소유자는 `GPURequest`로 전체 예산을 요청하고 `SharedMemoryChannel.spec.sessions=N`을 지정한다.
내부 사용자는 각 workload 컨테이너에 다음 자원을 요청한다.

```yaml
resources:
  requests:
    vmweave.io/gpu: 1
  limits:
    vmweave.io/gpu: 1
```

이 선언은 앞으로도 물리 GPU 1개가 아니라 **승인된 슬롯 1개**를 뜻한다.
초기에는 Pod당 GPU 컨테이너 1개, 컨테이너당 동시 CUDA client 1개를 지원한다.
GPU client가 추가 프로세스를 만들거나 DDP를 사용하는 기능은 별도 확장이다.
2개 슬롯이면 2개 Pod 실행, 세 번째 Pod는 슬롯 반환까지 Pending이어야 한다.
CUDA 작업만 끝나고 컨테이너가 살아 있으면 Kubernetes 예약은 계속 유지된다.

Kubernetes Extended Resource는 정수 단위이며 overcommit할 수 없으므로 `vmweave.io/gpu: 0.25`
같은 방식은 쓰지 않는다. [Kubernetes Device Plugin 계약](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/device-plugins/)

초기 A 단계는 동질 슬롯, VM 전체 메모리 예산 공동 사용으로 한다.
B 단계에서는 승인된 균등 분할 `slotPolicy.memoryBytes`와 정책 버전을 추가하는 안을 우선 구현한다.
필드의 위치는 Channel의 새 선택 필드로 하고 CRD·타입·admission·생성 도구를 함께 변경한다.
Worker와 Guest에 전달할 정책 원본은 외부 제어기가 생성하며 Pod 환경변수나 annotation을 권한 근거로 쓰지 않는다.

가변 VRAM 요청이 필요해지면 내부 DRA driver와 ResourceClaim을 별도 설계한다.
DRA consumable capacity는 여러 claim의 용량 배분을 표현할 수 있지만,
실제 메모리 집행을 대신하지 않으며 현재 외부 HAMi DRA 지원이 내부 VMWeave DRA 지원을 뜻하지 않는다.
내부 Kubernetes의 실제 버전/API/feature 상태를 확인한 뒤 선택한다.
[Kubernetes DRA capacity 설명](https://kubernetes.io/docs/concepts/resource-management/dynamic-resource-allocation/dra-features/)

**5. 코드 변경 묶음**

| 작업 | 수정·추가 대상 | 구현 내용 및 검증 |
|---|---|---|
| T1 VM·내부 클러스터 준비 | `scripts/operator/` 신규 orchestration 도구, 기존 `create-channel.py`, Guest 이미지 도구 | 영구 root PVC와 SHM PVC 구분, Halted VM 생성, 참조 UID 조회, binding 생성, 부팅, 내부 Kubernetes 준비를 단계화 |
| T2 다중 슬롯 제어 계약 | `operator/internal/engine/admission.go`, `lifecycle.go`, `persistent.go`, `operator/api/v1alpha1/types.go`, CRD/chart 사본 | sessions 1..승인 상한 검증, N>1은 호환 runtime 정책에만 허용, 실행 중 슬롯 수/정책 변경 거부 |
| T3 Guest supervisor | `guest_bootstrap.py`, 신규 `guest_supervisor.py`, `guest_broker.py`, service/install/package scripts | layout N개 파싱, 슬롯별 독립 process/env/socket/lock/status 생성. owner 생성·호출 thread 유지 |
| T4 discovery v2 | `guest_status.py`, Plugin의 `Discovery`/`Config.Check()` | `slots[]`에 slot ID/session ID/health/timestamp/reason/policy 정보. 공통 allocation/generation/boot/library identity 검증 |
| T5 다중 device 광고·할당 | `integrations/kubernetes-device-plugin/internal/plugin/plugin.go`, `cmd/main.go`, chart | device ID `vmweave-slot-i`, 개별 health 갱신, 컨테이너 요청별 결과, 선택 슬롯 directory만 mount |
| T6 슬롯별 메모리 정책 | `worker.go`, `supervisor.py`, `worker_sessions.c`, `cuda-dispatch/src/runtime.c`, `exec.c`, 실제 allocation 경로들 | 신뢰된 정책을 slot worker와 CUDA child로 전달, 지원 할당 경로별 accounting·OOM·rollback·회수 |
| T7 장애·관측 | `supervisor.py`, `guest_status.py`, Operator observe/readiness, 신규 내부 진단 도구 | 슬롯별 상태와 전체 VM 상태 구분, Pod↔slot↔epoch↔CUDA PID 대응, 재시작 시 fencing |
| T8 패키지·회귀 | Plugin/Guest/Worker 이미지, release lock, chart, tests, 사용 문서 | 버전 조합 고정, N=1 호환, N=2/4 E2E, clean install/upgrade/rollback 검증 |

파일 이름 중 신규 항목은 설계상 생성 예정이며 현재 존재한다고 가정하지 않는다.
역사 실험의 runner를 운영 설치기로 그대로 사용하지 않고, 필요한 동작만 일반화한 새 도구로 옮긴다.

T1의 상태 흐름은 `Prepared → Bound/Starting → GuestReady → ClusterReady → SlotsReady`로 나누고
각 단계의 실제 관측 조건을 명시한다. VM lifecycle은 `Stopped`에서 VM 시작 요청을 받아 binding을
만드는 현재 순서를 따른다. Allocation 모드의 수동 `BackingReady` 절차와 혼합하지 않는다.
API 조회 지연은 timeout/retry로 다루며, 새 Pod가 실행 가능한 상태를 단순 VM Running으로 판정하지 않는다.
단일 VM 개발 환경에서는 control-plane 노드의 workload scheduling 허용을 명시하고,
후속에는 별도 CP VM + GPU worker VM 구성을 지원한다.

`create-channel.py`는 현재 Request 생성 후 Channel 생성에 실패하면 Request가 남을 수 있다.
입력 전체 사전 검증, render/dry-run, 동일 UID·동일 spec에 한정한 재시도,
생성한 UID 기록과 미완료 상태 재개를 추가한다. 이름이 같다는 이유로 기존 자원을 덮어쓰지 않는다.

T4의 discovery v2는 `maxClients=N` 하나로 대체하지 않는다. 슬롯별 session ID를 실제 layout과 대조하고,
중복/범위 밖 ID, 오래된 generation, hash 불일치, symlink·경로 탈출·비신뢰 소유권을 거부한다.
32개 상태에서 현재 8 KiB JSON 상한이 충분한지 계산하고 제한을 명시적으로 갱신한다.
새 Plugin은 v1을 1슬롯으로 읽을 수 있게 하고, 구 Plugin이 v2를 읽으면 안전하게 광고를 중단하도록 한다.

T5의 `Allocate()`는 여러 ContainerRequests를 각각 검사하고 같은 요청 안의 중복 슬롯을 거부한다.
Kubelet이 예약의 기준이며 Allocate를 세션 OPEN 또는 영구 lease 생성 시점으로 쓰지 않는다.
재호출은 같은 슬롯 설정을 반환한다. API에 Pod UID가 직접 제공된다고 가정하지 않는다.
필요한 Pod 대응은 내부 노드의 kubelet PodResources API와 container/PID/cgroup 관측을 결합한다.
임의 annotation·자기 신고 Pod UID는 권한 증거가 아니다.

Pod에는 HostPath `/run/vmweave/slots/i`만 ContainerPath `/run/vmweave`로 읽기 전용 mount하고
`VMWEAVE_BROKER_SOCKET=/run/vmweave/gpu.sock`을 주입한다.
전체 `/run/vmweave`를 모든 Pod에 제공하면 다른 슬롯 socket 접근이 가능해지므로 피한다.
directory mount를 유지해 socket inode 교체를 관측하게 하되 기존 CUDA context 복구로 해석하지 않는다.
VM root/내부 cluster administrator는 신뢰 주체이며, 이 구조는 그 관리자에 대한 보안 경계가 아니다.

Guest 직접 GPU 프로그램도 초기에는 별도 예약 슬롯으로 분리하거나 운영상 실행을 금지한다.
소켓 GID만으로 Kubernetes 예약을 강제할 수 없으므로 임의 Guest 프로세스까지 강제 통제하려면
peer PID/cgroup과 내부 예약의 검증을 추가하고 실패 시 연결을 거부해야 한다.

**6. 메모리·compute 정책의 구현 조건**

외부 `VMWEAVE_MEMORY_BYTES`는 VM 전체 HAMi quota이며, 각 child가 상속해도 자동 N분할되지 않는다.
새 `slotMemoryBytes` 정책은 별도 전달하고 다음 불변식을 적용한다.

```text
sum(slot memory budgets) + measured runtime/context reserve <= VM memory budget
active CUDA clients per slot <= 1
advertised slots <= provisioned and approved slots
```

예를 들어 VM 16 GiB를 4개로 나눌 때 overhead 측정 없이 슬롯당 4 GiB를 보장하지 않는다.
남겨야 하는 공간에는 context, cuBLAS/cuDNN 내부 workspace, allocator cache 등의 실제 비용이 포함된다.
할당 거부 전후 accounting은 실패/중복 free/세션 종료에서 원자적으로 복구되어야 한다.
`cudaMemGetInfo`와 PyTorch allocator 관측도 슬롯 정책과 일치시키고, 기존 상태 캐시는 세션·정책 변경 시 무효화한다.

`cudaMalloc` 하나만 감싸서 완전한 VRAM 한도를 주장하지 않는다.
Driver allocation, async/pool, managed memory, library 내부 할당 등 지원 경로의 목록을 만들고
집행되지 않는 경로는 명시적으로 unsupported 처리하거나 검증된 외부 집행 수단을 적용한다.
라이브러리 내부 사용을 포함한 상한을 현 단일 Worker Pod 내에서 강제할 수 없는 경우,
B 단계 출시는 보류하고 슬롯별 별도 host Worker Pod/HAMi 할당 구조를 대안으로 평가한다.
그 대안은 현재 단일 `workerPodUID`·Attachment·DRA claim·회수 모델까지 바꾸므로 작은 수정이 아니다.

현재 compute 한도는 VM 전체 Worker에 적용된다. N개 슬롯을 만든다고 N개의 보장된 compute 분할이 생기지 않는다.
초기 A+B는 VM 전체 compute 한도 아래 경쟁하는 방식으로 명시한다.
향후 weighted scheduling은 긴 커널의 선점 불가·비동기 enqueue 편향을 고려해야 한다.
MPS 도입은 현재 `worker_guard()`가 MPS 환경을 거부하므로 별도 backend 검증과 설계가 필요하다.
MIG/passthrough 또한 현재 SHM runtime에 설정 하나로 추가되는 기능으로 다루지 않는다.

SHM backing은 슬롯당 두 개의 17 MiB arena와 ring을 갖고 전체를 2의 거듭제곱으로 올림한다.
현재 생성식 기준 1/2/4/8/16/32슬롯은 각각 64/128/256/512/1024/2048 MiB다.
32슬롯이면 예제의 1 GiB SHM PVC보다 크다. RAM·CPU·FD·memfd arena·pinned staging·CUDA context
사용량도 N과 함께 측정하고 VM/Worker requests·limits, PVC 용량, 배치 전 검사를 보강한다.
BAR mapping의 크기 자체를 프로세스 수만큼 실제 RAM 사용으로 단순 합산하지 않는다.

**7. 장애·업그레이드 계약**

| 사건 | 기대 동작 |
|---|---|
| Pod A 정상 종료/SIGKILL | A socket 정리, A epoch/child 회수, 동일 슬롯은 새 client에 새 epoch 부여. B 계산 계속 |
| A quota 초과 | A에 OOM, 회계 복구. B의 결과·세션 유지 |
| A CUDA child 장애 | A 세션 실패 처리 및 회수 확인 후 슬롯 재사용 여부 판정. B 유지 |
| A Broker/transport worker 장애 | A 슬롯 Unhealthy. 같은 소비된 ring에 프로세스를 단순 재시작하지 않음 |
| Plugin/kubelet 재시작 | 기존 CUDA 세션 유지, 기존 슬롯 ID로 재등록, 새 슬롯 중복 생성 금지 |
| VM/host Worker 전체 장애 | 모든 슬롯 신규 할당 차단, 실행 실패 명시. 이전 generation 복구를 가장하지 않음 |
| VM 재부팅·binding 재생성 | 기존 detach/회수 완료 후 새 allocation/generation. 앱은 새 CUDA 세션 필요 |

현재 [queue.c](../../runtime/shm/shm-queue/src/queue.c)의 `vmweave_shm_open()`은
소비된 ring 재연결을 거부한다. systemd `Restart=always`로 변경하는 방식은 사용하지 않는다.
초기에는 고장 슬롯을 격리하고 살아 있는 슬롯의 작업이 끝난 뒤 VM binding을 재생성한다.
VM 재부팅 후 기존 container의 mount/할당 캐시가 새 socket에 붙는 경우도 점검하고,
세션의 generation/epoch 검증 없이 이전 실행을 이어가지 않는다.

현재 supervisor는 모든 슬롯 marker가 있어야 전체 ready를 게시한다.
슬롯 하나의 장애가 전체 Worker 교체·VM drain을 유발하지 않도록 실제 Operator의 관측 흐름과
readiness 소비자를 함께 검증한다. 초기 전체 attach 완료와 이후 부분 장애를 다른 상태로 기록한다.
최종 Detached는 모든 child 종료·mapping 해제 후에만 보고한다.

업그레이드는 신규 capability/정책을 이해하는 Operator, Worker, Guest, Plugin의 조합으로 고정한다.
실행 중 슬롯 수·분할 한도 변경과 오래된 Broker를 같은 ring에 재기동하는 업그레이드는 허용하지 않는다.
롤백은 workload 종료 → 기존 binding drain/reclaim → 구 조합 설치 → 새 1슬롯 binding 순서로 검증한다.
이미 종료된 CUDA context를 롤백으로 복원한다고 약속하지 않는다.

**8. 단계별 개발 순서와 출구 조건**

| 단계 | 우선순위 / 작업 | 완료 조건 | 대략적 개발 노력 |
|---|---|---|---|
| P0 | 필수: 계약·환경 baseline, VM 준비 경로 확정 | N=1 기존 흐름, 이미지/ABI/내부 Kubernetes 버전·quota 단위·비교 기준 기록 | 2~3 인일 |
| P1 | 필수: T1/T2/T3의 N=2 transport | 새 VM에서 2개 Broker·2개 SHM 슬롯·2개 CUDA child 동시 실행, 단일 슬롯 회귀 통과 | 4~6 인일 |
| P2 | 필수: T4/T5 discovery·Device Plugin | 내부 Pod A/B 동시 계산, C Pending, A 종료 후 C 실행, 선택 슬롯 mount 확인 | 3~5 인일 |
| P3 | 필수: T6 메모리 한도 | A/B 서로 다른 데이터 검산, 경계/OOM/라이브러리 내부 사용·회수 검증; B 출시 가능 여부 판정 | 5~10 인일 |
| P4 | 필수: T7/T8 장애·패키지·N=4 | 장애 행렬, 반복 실행, 이미지 고정, 신규 설치·N=1 롤백·문서 완성 | 4~6 인일 |
| P5 | 후속: compute 정책·가변 크기·내부 DRA | 각각 별도 설계·측정으로 보장 수준 확정 | P3/P4 이후 산정 |

P0→P1→P2→P3→P4를 기본 순서로 한다. 총 18~30 인일은 1명 전담·GPU 시험 환경 가용을 가정한 추정이다.
P3에서 별도 Worker Pod 구조가 필요해지거나 CUDA 지원 범위를 넓혀야 하면 재산정한다.
P2까지는 A 수준의 개발 시연이며, P3/P4 전에는 “Pod별 GPU 자원 격리 완료”로 출시하지 않는다.
첫 변경 묶음은 계약/테스트, 다음은 runtime/Plugin, 그다음 quota/장애, 마지막은 설치/배포 검증으로 리뷰한다.

**9. 검증 행렬**

| ID | 시험 | 합격 기준 |
|---|---|---|
| V01 | N=1 회귀 | 기존 v1 discovery·직접 Guest·Plugin 경로와 지원 MLP/LSTM/CNN 조건 유지 |
| V02 | N=2, N=4 동시 실행 | 서로 다른 seed·출력, 실행 구간 겹침, slot/epoch/host PID 대응, 결과 전부 일치 |
| V03 | N+1 Pod | 추가 Pod Pending, 한 컨테이너 종료 후 예약 반환·새 epoch로 실행 |
| V04 | Pod 접근 경계 | 타 슬롯 directory/socket·BAR·host GPU device 미노출, 임의 slot/env 변조로 접근 불가 |
| V05 | 메모리 경계 | 한도 아래/같음/초과, 2개 동시 할당 경쟁, 해제 후 재할당. 다른 Pod 결과 정상 |
| V06 | lifecycle | 정상 종료/SIGKILL/100회 세션 교체 후 PID·FD·VRAM 잔류가 정의한 baseline으로 복귀 |
| V07 | 부분 장애 | 한 CUDA child 또는 Broker 장애 시 나머지 슬롯 작업 성공, 고장 슬롯 신규 할당 차단 |
| V08 | 제어 경로 재시작 | Plugin/kubelet 재등록 후 중복 예약·GPU 세션 중단 없음 |
| V09 | VM/Worker 장애 | 전체 실패 명시, 이전 generation 거부, 회수 후 새 binding에서 재실행 |
| V10 | quota·부하 공정성 | 총 VRAM 상한, 각 슬롯 메모리 상한, 처리량·지연·starvation 관측. compute 보장은 별도 판정 |
| V11 | 장시간·호환성 | 24시간 교대 부하, 지원 CUDA copy/stream/event·MLP/LSTM/legacy CNN 회귀, 미지원 API 명시 |
| V12 | 설치·업그레이드 | clean VM→내부 Kubernetes→Plugin→Pod 실행, v1/v2 혼합 거부, 중도 실패 재개·회수·롤백 |

V02는 프로세스가 여러 개 보이는 것만으로 통과시키지 않는다. barrier로 같은 시간에 부하를 시작하고
각 Pod에서 완료된 CUDA 연산과 검산 결과, host PID의 활동 구간을 함께 수집한다.
성능 기준은 동일 VM 전체 quota에서 1/2/4 Pod의 총 처리량·Pod별 지연·최대 대기시간이다.
확장에 따른 성능 개선은 측정 결과로 판단하고 선형 증가를 전제하지 않는다.

CPU 검사: `make operator-check`, `make test-control`, `make check-layout`, Plugin `go test -race ./...`
및 `go vet ./...`, discovery·owner·session IPC·quota mock 검사, chart packaging 검사를 변경 영역별 실행한다.
CUDA 빌드/회귀와 실제 VM 시험은 구분하고, E2E 증거는 새 실험 디렉터리에 source SHA·image digest·
VM/VMI/Pod UID·allocation/generation·slot ID·epoch·GPU UUID·오류·cleanup 상태를 기록한다.

**10. 이번 분석의 확인 범위와 남은 결정**

현재 소스에서 single-slot 제한과 N-slot 기반을 직접 확인했다.
로컬 기존 검사 `go test -race ./...`(Plugin) 및 `test_guest_status.py` 6개가 통과했다.
이 결과는 기존 단일 슬롯 코드의 검사이며 새 기능이나 실제 GPU 성공을 뜻하지 않는다.
문서 검사 결과는 작업 완료 보고에 기록한다.

첫 구현에서 정할 사항은 초기 VM 총 VRAM/compute 예산, 슬롯 수 2의 실제 자원 크기,
검증할 CUDA/PyTorch 이미지, 내부 Kubernetes 버전, B 단계의 지원 메모리 API 범위다.
이 값은 현재 공유 클러스터의 빈 GPU 상태나 과거 Lupine 계획의 snapshot에서 추정하지 않는다.
기존 [중앙 Operator 실습](../../experiments/nested-k8s-gpu/lab/CENTRAL-OPERATOR-LAB.md)을 준비 절차의 근거로 쓰되,
그 문서의 미실행 단계는 새 실행으로 검증한다.

이 계획은 VMWeave 개발 문서이며 별도 Lupine 실험 계획을 대체하지 않는다.
