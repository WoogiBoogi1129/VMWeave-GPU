# Go Operator 전환 검증: 2026-09-30

초기 중앙 Go Operator를 gpu-4에 배포했다. Controller와 Webhook은 `vmweave-system`의
`vmweave` release에 각각 1 replica로 실행한다. API는 `vmweave.io/v1alpha1`의
GPUProfile, GPURequest, SharedMemoryChannel, ChannelAttachment다.

[공개 검증 요약 JSON](../../experiments/operator/2026-09-30/summary.json)에 실행 결과,
UID, image digest, detach 증거와 비공개 원본의 해시를 기록했다.

## 구현과 검증

- Operator SDK v1.42.3, Go 1.25.6, controller-runtime v0.23.3, Kubernetes client v0.35.0.
- 실제 API 서버: Kubernetes v1.37.0, KubeVirt v1.9.0, HAMi 2.10.0.
- namespace별 cache, 참조 index, watch/queue, Lease election, health/ready 및 기본 controller-runtime metrics.
- 중앙 SA와 사용자 namespace별 RoleBinding, Worker 전용 SA/Role, TLS admission.
- 새 allocation은 UID를 포함한 Pod/SA/RBAC 이름을 사용하여 구API의 완료 이력과 충돌하지 않는다.
- Go 계약 테스트 13개: namespace 격리, dependency index, 일반 VM admission,
  중앙/Worker 신원, 세대·Pod UID, terminal 증거, Released 삭제, 과거 객체 보존. race/vet 통과.
- Python helper 테스트 52개 통과. 실험 분석 테스트 17개 중 10개 통과, 자료 의존 7개 skip.
- Helm lint, 새 CRD 4종 서버 검증·적용, schema 사본 비교, docs strict/link 검사 통과.
- review: 두 namespace의 동명 Channel이 서로 다른 UID로 처리되고 workload/finalizer 생성 없이
  status를 기록한다. 상태가 바뀌지 않을 때 resourceVersion이 안정적임을 확인했다.
- 실제 admission: 관리 범위 밖 Pod 생성 불가, 일반 VMI 허용, 잘못된 SHM binding 거부,
  올바른 Worker 보고 허용 및 다른 Pod UID의 보고 거부.

최종 Operator image:
`localhost/vmweave-operator@sha256:e9fdcc30a08a7a38b88dcd8dad0fe386c89687a87b0296da15e4dee8958d9cb6`.
이는 gpu-4의 로컬 OCI import 결과다. 공개 registry 게시나 다중 노드 image 배포 완료를 뜻하지 않는다.

## 실제 GPU 실행

모두 실제 Guest → SHM → HAMi Worker → GPU PTX 연산과 복사 검산을 수행했다.
정식 성능 비교나 전체 CUDA/PyTorch 호환성 시험은 아니다.

| 실행 | 관리 Controller 위치 | GPU 검산 | Ready / Released | 전체 실행 시간 |
|---|---|---|---|---|
| `vmweave-test-a/same-vm-3` | vmweave-system | PASS, 2,379 kernel repeats | 둘 다 확인 | 60.56초 |
| `vmweave-test-b/same-vm-3` | vmweave-system | PASS, 2,455 kernel repeats | 둘 다 확인 | 62.87초 |
| 기존 `flyt-evidence/evidence-perf-3-s` 이전 | vmweave-system | PASS, 2,363 kernel repeats | 둘 다 확인 | 64.92초 |

앞의 두 VM은 서로 다른 namespace의 동명 VM/Channel로 동시에 실행했다.
각각 다른 UID/allocation/Worker를 사용하고 guest·worker Detached 증거를 남긴 뒤 backing을 회수했다.
마지막 실행은 기존 VM/PVC UID를 유지하고 새 Request/Channel UID로 이전했다.

## 기존 배포와 데이터

- 소스 백업: `backup/pre-vmweave-operator-20260930`, backup 기록 커밋 `e045d31`.
- private restic: `309c7ee1`(기존 .local/artifacts/results), `0078f8c3`(기존 PV 디스크).
  전체 866 pack 읽기 검사를 통과했다. 온노드 백업이며 원격 재해복구 복제본은 아니다.
- `flyt-evidence`: GPUProfile 101개, GPURequest 101개와 선택 Channel 1개를 신API로 이전했다.
  구API Channel 100개와 Attachments 200개는 이력으로 보존했다. 이전 도구 재실행은 새 allocation을
  재활성화하지 않고 기존 신API UID와 drain 상태를 유지했다.
- `flyt-evidence`, `flyt-review-validation`의 구 Helm release는 이력을 보존하며 제거했다.
- **전환 예외:** `flyt-gpu-validation/shm-channel-a`는 기존부터 `Draining/AwaitingDetachEvidence`였다.
  guest launcher terminal 증거가 누락되어 구 Controller/Webhook과 API를 유지한다.
  새 Operator의 관리 목록에서 제외했으며 이전 도구의 apply 거부도 확인했다. 강제 회수하지 않았다.
- 관리 목록: `flyt-evidence`, `flyt-review-validation`, `vmweave-test-a`, `vmweave-test-b`.
  namespace 이름 자체를 변경하거나 기존 VM/PVC를 삭제하지 않았다.

## 작업 중 장애와 복구

백업 초기의 중복 파일 복사가 디스크 여유 임계값을 넘어서 kubelet DiskPressure와 Pod 퇴거를
유발했다. 사전 용량 판단이 부족했다. 디스크 원본과 실험 파일을 restic으로 보존하고 중복
빌드 산출물은 `restic dump`와 원본 SHA-256 대조 후 정리했다. 패키지 다운로드 cache도 정리했다.
이후 DiskPressure 해제, KubeVirt Deployment/DaemonSet readiness, 기존 `basic-vm`의 Running/Ready를 확인했다.

이미지 GC로 제거된 launcher/helper/Worker image를 복구했다. 첫 두 시험은 hook pull 지연으로
VM 부팅에 실패했으며 GPU PASS로 세지 않았다. 이 경우에도 terminal 관측 후 Released까지 회수했다.
기존 basic-vm에는 이전 UID의 KubeVirt ghost record가 남아 있었다. 구 Pod·socket·QEMU 부재를
확인하고 해당 record 하나를 백업한 뒤 제거하고 virt-handler를 재기동했다.
[관련 KubeVirt 오류 보고](https://github.com/kubevirt/kubevirt/issues/7032)와 같은 오류 메시지를 관측했다.

이전 시험에서는 구API의 완료 Pod와 이름이 충돌해 새 Channel이 준비 전에 중단됐다.
UID 기반 이름을 추가한 뒤 새 binding/VMI/소유 child/backing 모두 없음을 검증하고,
그 한 건의 새 allocation을 Reserved부터 재시도했다. 기존 Draining allocation에 이 복구를
적용하거나 detach 증거·finalizer를 강제로 바꾸지 않았다.

## 남은 범위

- C/CUDA runtime은 유지한다. supervisor/provision/reclaim/domain hook은 신API 호환 Python helper다.
- 구API 제거는 기존 Draining 해소와 이력 보존 확인 이후 별도 운영 작업이다.
- 전체 HA·API 단절·node fencing 장애 행렬 및 Terminating namespace 자동 회수는 미완료다.
- scope/mode 변경은 현재 자동 rolling 전환 대신 유지보수 절차를 사용한다.
- 초기 CRD 원본은 기존 CEL을 보존한 JSON schema이며 Go 타입/DeepCopy를 생성한다.
  Go markers를 schema 원본으로 바꾸는 작업은 후속으로 남긴다.
- prepare 이전 실패처럼 매핑 여부를 확인할 수 없는 상태는 자동 강제 회수하지 않는다.
