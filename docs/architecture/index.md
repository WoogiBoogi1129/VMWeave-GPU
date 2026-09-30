# 전체 구조

중앙 제어 영역은 `vmweave-system`의 Go Controller와 TLS Webhook입니다.
Operator SDK/controller-runtime 기반으로 namespaced cache, watch, 객체별 queue,
Lease leader election, health/ready endpoint와 metrics를 사용합니다.

```text
vmweave-system
  vmweave-controller ─── RoleBinding + namespace allowlist ──┐
  vmweave-webhook    ─── Service + ValidatingWebhook ────────┤
                                                           │
team-a / team-b                                             │
  GPUProfile → GPURequest → SharedMemoryChannel ←───────────┘
  KubeVirt VM → virt-launcher ↔ local PVC ↔ GPU Worker
  ChannelAttachment (guest / worker), prepare / reclaim Pod
```

4종 CRD는 `vmweave.io/v1alpha1`, Namespaced scope입니다. 참조는 같은 namespace의
이름과 UID로 검증합니다. Controller/Webhook의 ServiceAccount는 system namespace에 있고,
Worker는 자기 namespace의 전용 ServiceAccount로 자기 Channel/Attachment만 접근합니다.
Node/PV/Namespace의 단건 조회만 별도 ClusterRoleBinding으로 허용합니다.

관리 대상은 명시적인 allowlist입니다. Webhook namespaceSelector는 Kubernetes가 관리하는
`kubernetes.io/metadata.name`을 사용합니다. 같은 namespace의 일반 VM은 Channel 검사를
통과하도록 설계하며, SHM VM의 live migration은 거부합니다.

Go 제어기는 CUDA 호출을 실행하지 않습니다. C/CUDA Guest·Worker 경로와 Python helper의
signal·파일·domain XML 계약을 유지합니다. 공개 API 이름을 바꾸어도 기존 공유 메모리 ABI와
파일 경로까지 동시에 바꾸지 않습니다.

[수명 주기](lifecycle.md) · [권한·설정](../reference/configuration.md) ·
[전환 검증과 한계](../development/operator-validation.md).
