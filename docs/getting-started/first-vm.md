# 첫 VM 실행

관리자가 중앙 active Operator와 workload namespace를 준비한 뒤 실행합니다.
관리자는 PV와 승인 Profile을 준비하고, 사용자는 자기 namespace의 PVC·VM·Request·Channel을 생성합니다.

1. 관리자 승인 `GPUProfile`: 노드/GPU UUID, quota, 새 API 호환 Worker image.
2. 해당 노드의 local PV에 연결된 filesystem PVC.
3. 호환 Guest image를 쓰는 `runStrategy: Halted` KubeVirt VM.
4. VM UID와 Profile UID를 참조하는 `GPURequest`.
5. VM/Request/PVC UID를 참조하는 `SharedMemoryChannel`.

[Guest 준비](guest-images.md)를 먼저 완료합니다. 관리자는 [관리자 예제](../../deploy/examples/vmweave/admin.yaml)의
node/GPU UUID·Worker digest·local directory를 설정하고 QEMU UID/GID(검증 환경 107:107)에 맞는 권한을 줍니다.
검토 후 Profile의 `approved`를 true로 바꾸고 적용합니다.

```sh
kubectl apply -f .local/admin.yaml
```

사용자는 [사용자 예제](../../deploy/examples/vmweave/user.yaml)를 `.local/user.yaml`로 복사해
자기 namespace·관리자가 지정한 PV 이름·Guest digest와 SSH 공개키용 cloud-init을 설정합니다.
사용자에게 PV 생성이나 Profile 승인 권한을 부여하지 않습니다.

```sh
kubectl apply -f .local/user.yaml
```

API group은 `vmweave.io/v1alpha1`입니다. Kind는 `GPUProfile`, `GPURequest`,
`SharedMemoryChannel`, `ChannelAttachment`입니다. 참조는 모두 같은 namespace입니다.
신규 Channel에는 새 helper/Worker/hook image digest를 입력합니다. 과거 실행의 UID·allocation·status를 복사하지 않습니다.

```sh
python3 scripts/operator/create-channel.py --namespace team-a --vm gpu-vm \
  --profile approved-gpu --pvc gpu-backing --name gpu-request \
  --compute 25 --memory 1024Mi \
  --helper-image YOUR_HELPER_DIGEST_REFERENCE --hook-image YOUR_HOOK_DIGEST_REFERENCE
kubectl -n team-a get sharedmemorychannels.vmweave.io gpu-request -o yaml
```

생성 도구는 참조 UID를 조회하고 Request와 Channel을 생성합니다. Worker 이미지는 Profile에서 가져옵니다.
Profile 승인·PVC 준비·VM 실행까지 대신하지 않습니다.

## 자동 GPU smoke

VM은 `Halted`로 둔 채 Channel의 `BackingReady`를 기다립니다. VM을 수동으로 먼저 시작하지 않습니다.

```sh
kubectl -n team-a wait sharedmemorychannels.vmweave.io/gpu-request \
  --for=jsonpath='{.status.phase}'=BackingReady --timeout=180s
python3 scripts/run-evidence-smoke.py --namespace team-a --api-group vmweave.io \
  --name gpu-vm --channel gpu-request --key YOUR_KEY --artifacts YOUR_GUEST_ARTIFACTS \
  --output .local/new-vmweave-run
```

[Guest 준비](guest-images.md)의 SSH·artifact 조건이 필요합니다. 실행기가 VM 시작, 실제 GPU 연산,
Ready 확인, drain 및 Released 검증을 담당합니다. 출력 디렉터리는 매번 새로 지정합니다.
초기 인자·파일·Channel 상태 검사가 통과한 뒤의 실행 오류에는 drain을 시도합니다.
초기 검사 실패에는 자동 회수가 보장되지 않으므로 Channel 상태를 확인합니다.

중단된 시험의 Channel이 이미 Bound/Ready이고 재접속 조건이 맞을 때만 `--resume`을 사용합니다.
실행기는 종료 시 drain하므로 일반 애플리케이션이 사용 중인 Channel에 실행하지 않습니다.

## 수동 애플리케이션 실행

자동 smoke와 별도 경로입니다. `BackingReady` 확인 후 다음과 같이 시작합니다.

```sh
kubectl -n team-a patch vm gpu-vm --type=merge -p '{"spec":{"runStrategy":"Always"}}'
kubectl -n team-a get vmi,pods
kubectl -n team-a get sharedmemorychannels.vmweave.io,channelattachments.vmweave.io
```

Guest의 ivshmem BDF와 해당 allocation의 layout/slot을 프로그램에 전달해야 합니다.
[신규 실험](../evaluation/new-experiments.md)과 [SHM 계약](../../runtime/shm/shm-contract/README.md)을 확인합니다.
`Ready`는 mapping/Worker 관측이며 모든 CUDA 연산 지원을 뜻하지 않습니다.
종료 시 `spec.drain=true`를 요청하고 Released·detach 증거를 확인합니다.
Channel 삭제/namespace 제거 전에 회수를 완료하며 증거 없는 Draining은 강제로 해제하지 않습니다.
