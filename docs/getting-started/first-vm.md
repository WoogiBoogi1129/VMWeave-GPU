# 첫 VM 실행

관리자가 중앙 active Operator와 workload namespace를 준비한 뒤 실행합니다.
사용자는 자기 namespace에 다음 리소스를 생성합니다.

1. 관리자 승인 `GPUProfile`: 노드/GPU UUID, quota, 새 API 호환 Worker image.
2. 해당 노드의 local PV에 연결된 filesystem PVC.
3. 호환 Guest image를 쓰는 `runStrategy: Halted` KubeVirt VM.
4. VM UID와 Profile UID를 참조하는 `GPURequest`.
5. VM/Request/PVC UID를 참조하는 `SharedMemoryChannel`.

[workload 예제](../../deploy/examples/vmweave/workload.yaml)를 복사하고 실제 node/GPU UUID,
Worker/Guest digest로 변경합니다. 관리자는 해당 node에 local directory를 만들고
QEMU UID/GID(실험 환경은 107:107)에 맞는 권한을 설정합니다. 승인 후 `approved: true`로
변경하고 PV/PVC/Profile/정지 VM을 적용합니다. SSH smoke를 사용하려면 Guest image 또는
VM cloud-init에 사용자의 SSH 공개키를 설정합니다.

```sh
kubectl apply -f .local/workload.yaml
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

`BackingReady`를 확인한 후 VM을 시작합니다.

```sh
kubectl -n team-a patch vm gpu-vm --type=merge -p '{"spec":{"runStrategy":"Always"}}'
kubectl -n team-a get vmi,pods
kubectl -n team-a get sharedmemorychannels.vmweave.io,channelattachments.vmweave.io
```

`Ready`는 mapping/Worker 관측 결과이며 모든 CUDA 연산 지원을 뜻하지 않습니다.
호환 Guest 프로그램과 SSH key를 준비한 경우 다음 명령으로 GPU 실행 및 회수를 확인합니다.

```sh
python3 scripts/run-evidence-smoke.py --namespace team-a --api-group vmweave.io \
  --name gpu-vm --channel gpu-request --key YOUR_KEY --artifacts YOUR_GUEST_ARTIFACTS \
  --output .local/new-vmweave-run
```

실행기는 VM을 시작하고 실제 연산·Ready·Released 증거를 기록합니다.
실패 시에도 drain을 요청하므로 일반 애플리케이션을 실행 중인 Channel에 사용하지 않습니다.

종료 시 Channel의 `spec.drain=true`로 요청하고 `Released` 및 detach 증거를 확인합니다.
Channel 삭제/namespace 제거 전에 회수를 완료합니다. 증거가 없는 Draining을 강제로 해제하지 않습니다.
