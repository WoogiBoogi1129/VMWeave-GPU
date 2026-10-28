# 2노드 Kubernetes 및 VMWeave GPU Pod 실험 결과

실행일: 2026-10-28 KST · 기능 판정: **PASS**

새 VM 두 대에 Kubernetes Control Plane과 Worker를 구성했고, Worker VM 안의 비특권 Pod에서
VMWeave broker를 통해 실제 호스트 GPU 연산을 수행했다. Pod A/B의 정확성·세션 회수·재사용,
계획한 종료·재시작·VM 재생성·broker 수동 복구·메모리 quota 조건 모두 통과했다.

**해석 제한:** 종료 후 외부 리소스 대조에서 운영 시험 도중 HAMi Device Plugin, DRA plugin,
modelserve의 재배포가 확인됐다. 아래 PASS는 관측한 기능 결과다. 운영 시험 중 외부 환경이
불변이었다거나 다른 변경의 영향을 완전히 분리했다는 결론은 내리지 않는다.
조건별 단일 실행이며 장기 안정성·성공률·성능 격리를 검증한 결과도 아니다.

## 구성과 현재 상태

| 항목 | 값 |
|---|---|
| 외부 namespace | `vmweave-nested-k8s` |
| 실험 전용 Operator | `vmweave-nested-system`, 기존 배포와 동일 image digest |
| Control Plane | `vw-k8s-cp-01`, 4 vCPU / 8 GiB / root PVC 40 GiB, Node IP `10.245.0.10` |
| Worker | `vw-k8s-worker-01`, 4 vCPU / 16 GiB / root PVC 80 GiB, Node IP `10.245.0.11` |
| 내부 Kubernetes / CRI-O / Cilium | 1.35.9 / 1.35.10 / 1.20.2 |
| Guest OS / kernel | Ubuntu 22.04.5 / 5.15.0-191-generic |
| 망 | Guest WireGuard, Cilium VXLAN; Pod `10.246.0.0/16`, Service `10.247.0.0/16` |
| 최종 MTU | Guest eth0 1280, WireGuard 1220, Cilium 기준 1220 / 노드 간 route 1170 |
| GPU UUID | `GPU-7d708c42-8d4a-16d5-0746-474567157aa3` |
| Worker VM GPU quota | compute 50%, memory 2048 MiB, 동시 CUDA client 1개 |
| GPU 연결 | Guest library + `/run/vmweave` read-only hostPath + broker socket |
| GPU Pod 보안 | UID 1000 / 실제 vmweave GID 998, non-root, capabilities ALL drop, RuntimeDefault seccomp |

내부 Kubernetes에 GPU Device Plugin이나 별도 GPU Extended Resource를 만들지 않았다.
GPU Pod는 Worker hostname으로 배치하고 runner가 순차 실행한다. 내부 Kubernetes가 GPU
예약량·동시 사용을 스케줄링한다고 해석하지 않는다. compute 50%는 설정값이며 정밀한 성능 비율은 측정하지 않았다.

새 VM 2대, 내부 클러스터, GPU Channel은 검토용으로 유지했다. CPU 시험 부하는 제거했고
GPU Job은 모두 종료됐다. 의도한 실패 대조 Job의 Failed 상태는 증거로 남아 있다.
**GPU quota 예약은 계속 유지된다.** [접속·재현·복구 안내](HANDOFF.md)를 따른다.

## 조건별 결과

| ID | 실제 수행 | 결과·핵심 증거 |
|---|---|---|
| Guest 사전 확인 | 기존 smoke 1회 | 메모리·PTX 실행 PASS. 기존 binary의 내장 10초 루프를 사용했으며 추가 smoke는 실행하지 않음 |
| K1 | 수정된 망에서 1세트 | 30초 간격 두 Node Ready, 노드 간 HTTP·양방향 ICMP·DNS·ClusterIP·MTU 경계·Deployment Pod 재생성 PASS |
| G1/G3 | Pod A → B 각 1회 | 각 32 MiB, H2D → PTX vector kernel 1회 → sync → D2H → 전 원소 비교 → free, 회수 후 B 제출 PASS |
| G2 | 소켓 없는 Pod 1회 | GPU API 실패, 해당 Worker의 활성 CUDA 자식 없음 |
| G4 | 정상 삭제 1회 / SIGKILL 1회, 각각 후속 Pod 1회 | CUDA 자식 회수 및 후속 정확성 PASS. SIGKILL exit 137. 정상 삭제부터 회수 관측까지 1.90초 |
| G5 | kubelet restart 1회, 후속 Pod 1회 | kubelet PID 변경, 기존 Pod·세션 유지 및 완료, 후속 정확성 PASS. 재시작 후 Ready 확인 2.41초 |
| K2 | Worker Halted→Always 1회, 후속 Pod 1회 | Stopped/RuntimeReclaimed 확인, 새 VMI·allocation·generation·GPU Worker, Node UID·root 상태 유지. GPU 검증 완료까지 **118.87초** |
| K3 | CP Halted→Always 1회, 후속 Pod 1회 | 중단 중 API 접근 실패, 복구 후 etcd/CA·cluster/Node UID 유지. GPU 검증 완료까지 **99.55초** |
| Q1 | 3 GiB 할당 시도 1회, 후속 32 MiB 작업 1회 | `cudaMalloc` 오류 **2**, Pod CPU OOM 아님. 후속 정확성·회수 PASS |
| G6 | broker stop 1회, 새 VM runtime 복구 후 Pod 1회 | 진행 중 앱의 `cuLaunchKernel` 오류 **999** 관측. service만 재시작하지 않고 VM runtime 교체. 복구 명령 시작부터 후속 성공까지 **145.74초** |

GPU Pod는 정상·대조·장애 조건을 합해 총 15개를 제출했다. 그중 정확성 완료가 필요한
10개 Pod에서 각각 **8,388,608개 정수 원소, 불일치 0개, checksum 18014393673449472**를 확인했다.
checksum은 결과 수집 후 별도 Python 계산으로도 대조했다. 정상 GPU 프로그램은 각 실행에서 kernel을 한 번만 호출했다.
13개 활성 GPU Pod에서 호스트 GPU PID와 CUDA 자식 PID 대응을 수집했다. 소켓 없는 대조와
즉시 거부되는 quota 초과 작업에는 활성 GPU 관측 대기를 넣지 않았다.

정상/종료 조건의 CUDA 회수 관측은 60초 기준 이내였다. 수집된 컨테이너 종료 시각부터
회수 관측까지 최대 약 6.30초이며, API polling·관측 지연과 초 단위 종료 timestamp가 포함된다.
이 수치는 성능 benchmark 결과가 아니다. G6은 기존 세션의 자동 회수를 보장하는 시험이 아니라 수동 runtime 복구 시험이다.

## 실제 GPU 실행 대응

| Pod | 내부 Pod UID | 호스트 GPU PID | 외부 GPU Worker PID namespace의 CUDA 자식 |
|---|---|---:|---:|
| A | `a1a7a9eb-d611-44c4-85f7-3acd9bae8729` | 2556323 | 1047 |
| B | `1e434806-6aa1-48dc-95b4-1debbef7c313` | 2557429 | 1060 |

GPU UUID, `/proc/<pid>/status`의 NSpid, cgroup의 GPU Worker Pod UID를 함께 대조했다.
각 활성 관측에서 CUDA 자식은 1개였고, A 종료·회수 확인 후 B를 제출했다.
세부 연결은 [object-identities.json](object-identities.json),
[A 활성 관측](gpu/g1-a-active.json), [B 활성 관측](gpu/g1-b-active.json),
[A 결과](gpu/g1-a-final.log), [B 결과](gpu/g1-b-final.log)에 있다.

baseline broker가 client별 임의 epoch를 로그로 노출하지 않아 그 값 자체는 수집하지 않았다.
Channel session ID, allocation/generation, 순차 실행 구간, Pod UID와 실제 CUDA 자식 PID로 연결했다.
broker epoch까지 직접 수집한 완전한 trace라고 주장하지 않는다.

## 실행 중 수정과 외부 변경

설치기 commit `25b80e29bf2de6ec2363f052ea26e5c56210eb03`의 공통 준비·패키지 설치·init/join·Cilium 단계를 재사용했다.
CRI-O 저장소 403, 설치기 init 루프 변수 범위, Podman 옵션, 기본 bridge CNI,
CPU ICMP 권한, 터널 MTU, Cilium API endpoint를 실행용 복사본/새 Guest 설정에서 보완했다.
초기 K1 실패는 [cluster/attempt1](cluster/attempt1/)에 남기고, 네트워크 변경 영향을 받는 K1을 재검증했다.
GPU 조건은 성공 후 반복하지 않았다. 상세 경위는 [errors.md](errors.md),
설치 변경은 [installation](../../installation/)에 있다.

최종 대조에서 확인한 실험 외 리소스 변경:

| KST | 리소스 | API 기록 |
|---|---|---|
| 18:27:52 | `vmweave-dra-driver/hami-dra-driver-kubelet-plugin` | manager `helm` update, Pod 교체 |
| 18:28:38 | `kube-system/hami-device-plugin` | manager `kubectl-rollout`, restartedAt 변경, Pod 교체 |
| 18:29:43 | `aap-mp-control/modelserve` | manager `kubectl-client-side-apply`, 새 ReplicaSet/Pod |

이 runner의 변경 대상에는 위 리소스가 포함되지 않는다. API manager는 실행 주체의 신원을 증명하지 않는다.
교체된 Pod는 최종 조회에서 모두 Running/Ready였고, 기존 `vmweave-test-a/vmweave-k8s-01`의
VM runtime·GPU Worker·Channel·allocation/generation 식별자는 그대로였다.
[대조 결과](inventory/protected-comparison.json)와 `inventory/concurrent-*.json` 및 이벤트 원본을 보존했다.

변경은 종료 후 대조에서 발견됐으므로 운영 시험 중 환경 불변 조건이 유지됐다고 볼 수 없다.
특히 K2와 같은 시간대의 HAMi/DRA 변경 영향을 단독으로 분리하지 않았다. 관측한 성공을 기록하고,
외부 환경을 고정한 복구 성능·장애 격리 검증으로 확대하지 않는다.

## 시간과 재현 자료

- 기록된 환경 생성 시작: **17:47:15 KST**, 마지막 G6 복구 검증 완료: **18:34:20 KST** — 약 **47분 6초**.
- GPU 조건별 시험 시작: **18:26:00 KST**, 마지막 완료: **18:34:20 KST** — 약 **8분 20초**.
- 앞선 시간은 설치·이미지 다운로드·네트워크 진단/수정에 사용됐다. 결과 정리 시간은 위 구간에 포함하지 않았다.
- [versions.json](versions.json), [verification.json](verification.json), [timings](timings/),
  [manifests](../../manifests/), [runner](../../runner/), [workloads](../../workloads/), [SHA256SUMS](SHA256SUMS).

이는 이번 환경에서 측정한 실제 경과 시간이다. 다른 환경의 설치 시간이나 성공 확률을 보장하지 않는다.
