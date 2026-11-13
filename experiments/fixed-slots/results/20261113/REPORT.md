# 고정 2슬롯 구현 및 실제 VM 검증

2026-11-13 (Asia/Seoul). 미배포 작업 트리 후보.
기준 commit은 `7fa6ac673640045ab95c29ea085dd0b7c3ee81ff`이며,
[변경 소스·바이너리 hash](candidate-source.json), [실제 이미지 식별자](candidate-images.json),
[설치 Guest 파일 hash](guest-installed-hashes.json)를 별도로 기록했다.

**결과: 고정 2슬롯의 동시 실행·예약·정상 회수·회수 확인 후 재사용·Broker 부분 장애 차단을 실제 GPU에서 확인했다.**
Pod별 VRAM/compute 보장, 강제 삭제 직후 무조건 성공하는 재할당, 고장 Broker의 자동 복구는 제공하지 않는다.
공개 v0.1.2에 설정만 추가하는 기능이 아니며 후보 Operator·Guest control·Plugin을 함께 사용해야 한다.

## 구현 범위

- Operator: VM lifecycle에서 승인된 1~2 sessions 허용. 기존 immutable Channel 계약 유지.
- Guest bootstrap: layout을 한 번 읽고 슬롯마다 독립 Broker 프로세스 시작.
  프로세스별 환경변수, 자식 회수, 서비스 종료 처리, 같은 부팅에서 consumed ring 재시작 차단.
  한 Broker 종료로 정상 Broker를 함께 종료시키지 않는다.
- Discovery: 1슬롯의 기존 경로/schema v1 유지. 2슬롯은 슬롯별 schema v2 파일에
  slotIndex/slotCount/sessionID 추가. 통합 세션 관리자나 새 CRD/DB는 만들지 않았다.
- Plugin: 1~2개의 고정 device 광고, 슬롯별 health, 실제 boot layout과 상태 identity 대조,
  컨테이너별 1개 장치 할당 및 선택 슬롯 directory만 읽기 전용 mount.
- 실험 중 확인한 기존 미배치 Worker 회수 문제를 보완했다. 삭제 중이며 nodeName이 없고,
  container 관측이 전혀 없는 소유 Worker에 한하여 UID를 검증한 후 미실행 detach 증거를 기록한다.
  배치된 Worker·타 소유자·다른 UID에는 적용하지 않는다.
- CUDA C 코드, SHM ABI, Host supervisor 및 persistent Worker는 변경하지 않았다.

## 환경

| 항목 | 실제 값 |
|---|---|
| 외부 namespace | `vmweave-fixed-slots-exp` |
| 격리 Operator namespace | `vmweave-fixed-slots-system` |
| VM | 새 `fixed-slots-01`, 4 vCPU / 8 GiB, 영구 root disk 35 GiB |
| Guest | Ubuntu 22.04, kernel 5.15 |
| 내부 Kubernetes | v1.35.9, CRI-O 1.35.10, Cilium 1.20.2 |
| 내부 maxPods | 110, GPU 슬롯은 별도로 1 또는 2 |
| Host GPU | gpu-4의 GPU 2, `GPU-7d708c42-8d4a-16d5-0746-474567157aa3` |
| VM 총 HAMi 예산 | 2048 MiB / compute 25%, 2슬롯 공동 사용 |
| Guest C library | `08ccac5fb763451e448a68700f6156a6e0eba62950614913fb07c62ba966cfa0` |
| Worker/Helper/Hook | [기존 공개 digest](runtime-images.json) |

별도 Operator는 시험 namespace만 관리했다. 기존 CRD·중앙 Operator를 교체하지 않았다.
GPU 2는 기존 VM과 공유하므로 이 결과는 성능 벤치마크나 물리 GPU 독점 시험이 아니다.

## 실제 GPU 결과

[1슬롯 summary](single-ready/summary.json), [2슬롯 summary](two-reaped/summary.json),
[PID 대응 및 수치 분석](two-reaped/analysis.json).

| 검증 | 결과·증거 |
|---|---|
| 기존 1슬롯 | PASS. 128×128 SGEMM 27회, 매회 16,384개 원소 검산. [로그](single-ready/single.jsonl) |
| 2개 Pod 동시 실행 | PASS. A seed=3, B seed=11, 서로 다른 slot 및 CUDA PID. 실행 구간 18.486초 중첩 |
| 수치 정확성 | A 176회, B 628회, 총 13,172,736개 원소 일치. [A](two-reaped/a.jsonl), [B](two-reaped/b.jsonl) |
| 접근 범위 | 선택 슬롯 directory만 `/run/vmweave`에 read-only mount. peer directory/layout/NVIDIA device 미노출. [A mount](two-reaped/a-mountinfo.txt), [접근 확인](two-reaped/a-access.txt) |
| 중복 client | 두 슬롯 모두 두 번째 client의 cudaMalloc이 busy 코드 46으로 거부됨. [A](two-reaped/a-duplicate.txt), [B](two-reaped/b-duplicate.txt) |
| Plugin 재시작 | 두 GPU 작업의 진행을 유지하며 재등록 성공 |
| 세 번째 Pod | `Insufficient vmweave.io/gpu`로 Pending. [Pod C](two-reaped/c-pending.json) |
| 정상 종료·재사용 | A 종료 후 C가 slot 0 사용. 기존 CUDA PID 회수 및 새 PID 확인, B PID 유지 |
| 강제 종료·재사용 | C 강제 삭제 후 **실제 CUDA child 회수 확인 뒤** D가 slot 0 사용. 새 PID 확인, B PID 유지 |
| Broker 부분 장애 | slot 0 Broker SIGKILL 후 allocatable 2→1. B는 계산 완료, D는 실패, E는 대기. [최종 node](two-reaped/after-broker-fault-node.json), [B 완료](two-reaped/b-final.json), [E](two-reaped/e-pending.json) |
| Broker 자동 재시작 금지 | 서비스는 정상 peer를 유지하며 `NRestarts=0`. [기록](broker-service-after-fault.log) |

CUDA PID 변화는 `nvidia-smi`와 Worker Pod UID가 포함된 cgroup으로 확인했다.
컨테이너 PID namespace의 NSpid/PPid를 transport worker의 slot 인자와 연결했다.

| 시점 | slot 0 Host CUDA PID | slot 1 Host CUDA PID |
|---|---:|---:|
| A+B 동시 실행 | 1088841 | 1088872 |
| A 정상 종료 → C | 1090731 | 1088872 |
| C 강제 종료·회수 확인 → D | 1091095 | 1088872 |

원자료: [동시 실행](two-reaped/concurrent-cuda-processes.json),
[정상 재사용](two-reaped/after-graceful-reuse-cuda-processes.json),
[강제 종료 후 재사용](two-reaped/after-forced-reuse-cuda-processes.json),
[회수 확인](two-reaped/forced-child-reaped.json), [Worker 프로세스](two-reaped/worker-processes.json).
이 결과는 애플리케이션 동시 실행을 입증하며 GPU 커널의 하드웨어 동시 실행을 측정하지 않았다.
세션 epoch 값은 새 로깅을 추가해 수집하지 않았고, 실제 CUDA child 교체를 검증했다.

## 발견한 제한과 실패 기록

1. **강제 삭제 직후 즉시 재할당은 보장하지 않는다.** 첫 강제 삭제 시험의 D는
   기존 C가 아직 살아 있어 `busy(46)`로 실패했다.
   [실패 summary](two-mount-fixed/summary.json), [D 오류](two-mount-fixed/d.jsonl).
   중복 연결을 허용하지 않는 동작이며, 최종 시험은 실제 child 회수 확인 후 재사용을 검증했다.
   API 객체 삭제가 실제 프로세스 종료를 기다리지 않는 점은
   [Kubernetes의 강제 Pod 삭제 계약](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-termination-forced)과 일치한다.
   정상 종료를 우선하고 강제 종료 시 회수 확인 또는 새 애플리케이션 실행의 재시도가 필요하다.
2. **Broker SIGKILL은 즉시 Host CUDA 자원 회수를 뜻하지 않는다.** 고장 slot 0의 CUDA child
   PID 1091095와 562 MiB가 남았다. [실제 관측](two-reaped/after-broker-fault-cuda-processes.json).
   신규 할당은 차단되며 이 슬롯은 VM 전체 정지·binding 회수로 복구해야 한다.
   정상 slot의 완료는 확인했지만 공유 VRAM 고갈이나 GPU 자체 장애의 영향 격리는 보장하지 않는다.
3. 초기 GPU 1 선택은 HAMi 등록 목록에 없어 Worker가 미배치됐다. 단순 `nvidia-smi`의 유휴 여부로
   선택해서는 안 된다. 이후 등록된 GPU 2를 사용했다.
   이때 미배치 Worker가 detach 증거 없이 남는 기존 회수 문제를 수정했고,
   [미배치 Pod](unscheduled-worker.json), [실제 Reclaimed 관측](unscheduled-reclaim-observation.json)을 보존했다.
   finalizer 강제 제거나 SHM backing 강제 삭제는 하지 않았다.
4. 시험 도구의 Channel 재시도 두 개가 겹쳐 중단·정리하고 로컬 flock으로 순차 실행했다.
   Channel 교체 시 정지 VM의 이전 binding annotation도 정리해야 했다.
   Operator의 다른 Channel 소유권 거부를 우회하지 않았다.
5. 내부 Cilium 이미지 다운로드 중 node taint 때문에 Plugin의 desired Pod 수가 0이었다.
   초기 [1슬롯 준비 시간 초과](single/summary.json)는 GPU 실행 실패가 아니다.
   CNI Ready 후 같은 경로의 [회귀 시험](single-ready/summary.json)이 통과했다.
6. 최초 동시 실행의 mountinfo 검사기가 `/run` tmpfs의 상대 root `/vmweave/slots/0`을
   인식하지 못했다. [최초 기록](two/summary.json)을 보존하고 mount root 표현을 올바르게 파싱했다.
   이후 두 별도 슬롯의 read-only mount 및 CUDA 실행을 확인했다.

## CPU 검사

- `make test-control`: 138개, 성공(환경 조건에 따른 skip 1). [로그](control-tests.log)
- `make operator-check`: race-enabled Go tests / vet / manifest 검사 통과. [로그](operator-check.log)
- Plugin `go test -race ./...`, `go vet ./...`: 통과. [로그](plugin-tests.log)
- Plugin packaging 및 chart 1/2 허용·3 거부: 통과. [로그](packaging.log)
- `make check-layout`: 통과. [로그](layout.log)
- `make docs-check`: 통과. HTML 89개 및 검색 항목 299개 검증. [로그](docs-check.log)

모의/CPU 검사는 schema·slot·generation 불일치, stale/missing status, 파일 경로 신뢰,
할당 요청과 개별 health 알림, bootstrap의 프로세스 분리·자식 회수,
미배치 Worker 회수의 소유권/UID/실행 여부 조건을 확인한다. 실제 GPU 증거와 구분한다.

## 정리 상태

실험 Pod namespace들은 UID를 확인하고 제거했다.
VM 정지 후 Channel `Stopped`, VMI/Worker 제거, 해당 Worker cgroup에 속한 CUDA 프로세스 0개를
확인했다. Broker 장애 후 남았던 PID 1091095도 회수됐다.
[정지 전환](final-stop-transitions.json), [최종 Channel](channel-final-stopped.json),
[GPU 관측](gpu-after-stop.json), [외부 정리 결과](outer-cleanup.json).

시험용 VM·PV/PVC·Operator Helm release·관리 Pod·두 namespace를 제거했다.
재현용 root disk와 빌드 산출물은 `.local/fixed-slots-20261113/`에 남겼으며,
활성 VM 또는 GPU 예약은 남기지 않았다. 기존 VM/VMI 9개 객체의 UID·spec·상태,
GPUProfile 7개의 spec이 바뀌지 않았음을 [비교 확인](existing-environment-preserved.json)했다.

설치/연결용 개인 키와 kubeconfig는 결과 디렉터리에 포함하지 않았다.
공개 registry 업로드·릴리스 발행·commit/push는 수행하지 않았다.

[재현 절차와 실행기](../../README.md)
