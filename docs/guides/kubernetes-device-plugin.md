# VM 내부 Kubernetes Device Plugin

VMWeave Guest의 기존 GPU quota를 내부 Kubernetes에서 예약하고 연결하는 선택 설치 기능이다.
자원은 `vmweave.io/gpu: 1`, 지원 범위는 **할당 컨테이너당 동시 CUDA client 1개**다.
이 값은 물리 GPU 1개나 추가 VRAM 할당을 의미하지 않는다.

현재 검증 릴리스는 [device-plugin-v0.1.1](https://github.com/WoogiBoogi1129/VMWeave-GPU/releases/tag/device-plugin-v0.1.1)이다.
[배포물·digest 기록](../../deploy/releases/device-plugin-v0.1.1.json)과
[공개 배포물의 실제 VM 검증](../../deploy/releases/evidence/v0.5.9/README.md)을 함께 확인한다.
기본 LSTM 경로에는 v0.5.9 Worker와 새 Guest package를 함께 사용한다.

## 설치 전 준비

- 외부 VMWeave의 VM lifecycle 연결과 Guest Broker가 정상이어야 한다.
- 상태 조회를 제공하는 Guest package를 새 GPU binding 전에 설치한다.
  [Guest 준비](../getting-started/guest-images.md)를 따르고 실행 중 Broker의
  파일을 바꾸거나 같은 SHM rings에 Broker를 단순 재시작하지 않는다.
- Plugin·Guest package·workload 이미지는 같은 검증 릴리스의 digest를 사용한다.
- `getent group vmweave`로 실제 GID를 확인한다. 설치 대상 노드들의 GID를 일치시키고
  일반 사용자의 Pod 예제에도 같은 `supplementalGroups`를 사용한다.
- `sha256sum /opt/vmweave/lib/libvmweave_guest.so` 결과를 기록한다.
  Plugin은 이 hash와 Broker가 보고하는 hash의 일치를 요구한다.
- VM 직접 GPU 프로그램과 내부 Pod를 동시에 실행하지 않는 초기 운영 조건을 적용한다.
  Plugin은 VM 직접 프로세스를 예약·차단하지 않는다.

일반 사용자는 VM의 native NVIDIA driver나 장치 파일을 Pod에 넣지 않는다.
Plugin 설치는 내부 클러스터 관리자 권한이 필요하며, 외부 클러스터 자격증명은 필요하지 않다.

## 관리자 설치

아래의 이미지 digest와 hash는 실제 검증 산출물 값으로 교체한다.
`device-plugin-v*` 릴리스는 이미지 digest·소스 label을 담은 `images.json`,
`guest-identity.txt`, Helm chart 및 `images.docker.tar.gz`를 함께 제공한다.
레지스트리 읽기 권한 없이 설치할 때는 릴리스 파일을 내려받아 `sha256sum -c SHA256SUMS`로
검증하고 노드의 CRI image store에 archive를 가져온다. 가져오기 후 해당 런타임이 보고하는
RepoDigest를 확인하여 chart와 workload에 사용한다. Docker/별도 Podman store에만 load하면
kubelet이 이미지를 볼 수 없으므로 실제 CRI store를 확인한다.

```sh
kubectl label node YOUR_GPU_VM vmweave.io/device-plugin=enabled
helm upgrade --install vmweave-device-plugin charts/vmweave-device-plugin \
  --namespace vmweave-device-plugin --create-namespace \
  --set image.digest=sha256:YOUR_PLUGIN_IMAGE_DIGEST \
  --set librarySHA256=YOUR_GUEST_LIBRARY_SHA256 \
  --set brokerGID=YOUR_VMWEAVE_GID
kubectl get nodes -o custom-columns=NAME:.metadata.name,GPU:.status.allocatable.vmweave\\.io/gpu
```

Plugin DaemonSet은 선택한 노드에만 설치된다. 내부 클러스터의 admission 정책이
관리용 hostPath와 root 실행을 허용하는 namespace를 사용한다. 일반 GPU workload는 non-root다.
실제 GPU가 없는 노드에 임의의 상태 파일을 만들어 자원을 등록하지 않는다.

v0.1.1의 공개 OCI chart 설치 예시는 다음과 같다. Guest package 준비와 실제 GID 확인 후 실행한다.

```sh
helm upgrade --install vmweave-device-plugin \
  oci://ghcr.io/woogiboogi1129/charts/vmweave-device-plugin --version 0.1.1 \
  --namespace vmweave-device-plugin --create-namespace \
  --set image.digest=sha256:dafbc657529fc135709394f7f109a260e150cb5c18e455c004278adf45176c04 \
  --set librarySHA256=3b3644f42ae3d075c08c22e2578e59553e29c5a446f65cf41f33ad68a070a4a9 \
  --set brokerGID=YOUR_VMWEAVE_GID
```

Guest package 이미지:
`ghcr.io/woogiboogi1129/vmweave-device-plugin-guest@sha256:9cbbfb6c1501c84103f5e0f2fc921f384b11eea168a0f6971d7beb67b5384411`.
지원 workload 이미지:
`ghcr.io/woogiboogi1129/vmweave-device-plugin-workload@sha256:0277bb187c613a943e7568a1acfc6f4d6e76e95273742c144ae38dffc4cfdbdb`.

## 일반 사용자 실행

[Pod 예제](../../integrations/kubernetes-device-plugin/workloads/pod.yaml)의 workload image digest와
`supplementalGroups`를 설치 환경에 맞게 설정하고 제출한다.
Plugin이 소켓 디렉터리와 환경변수를 주입하므로 Pod에 hostPath·소켓 경로를 직접 지정하지 않는다.
지원 workload image는 Guest library 경로가 미리 설정되어 있다.

```yaml
resources:
  limits:
    vmweave.io/gpu: 1
```

이 조각 외에 CPU·메모리·권한 설정은 전체 예제를 따른다. 임의 CUDA/PyTorch image의
자동 호환성이나 다중 GPU 프로세스를 보장하지 않는다. SGEMM 검산은 같은 workload image에서
`command: ["/opt/vmweave/bin/sgemm"]`으로 실행한다. 선택 인자 `args: ["15"]`는
CUDA 메모리 할당 후 15초 대기하여 idle client 상태를 검증한다(0~60초).

자원이 하나뿐인 시험 클러스터에서는 A가 할당받은 동안 B는 Pending이다.
A의 CUDA 작업만 끝나고 컨테이너가 계속 실행 중이면 자원은 계속 할당된 상태다.
컨테이너 종료와 Kubernetes 자원 반환, Broker CUDA 세션 회수를 각각 확인한다.

## 공식 PyTorch 이미지의 검증 조건

공식 `pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime`을 그대로 사용한
[기능 검증](../../experiments/device-plugin-pytorch/results/20261106-official/REPORT.md)에서
CUDA 인식·전송·덧셈·행렬곱과 작은 5-step FP32 MLP 학습이 통과했다.
당시 v0.1.0 조합의 기본 `Linear` 경로는 cuBLASLt에서 exit 139로 실패하므로,
PyTorch import 전에 `DISABLE_ADDMM_CUDA_LT=1`을 적용한다. 이 조건에서 SGD 기본 옵션도 통과했다.

Guest library는 공개 Guest 이미지의 initContainer가 emptyDir에 복사하고 hash를 확인한다.
공식 PyTorch 컨테이너는 이를 읽기 전용 mount하며 `LD_PRELOAD`, adapter의 `LD_LIBRARY_PATH`,
`VMWEAVE_MIRROR_DEVICE_VA=1`을 설정한다. Plugin이 broker 소켓을 주입한다.
공식 wheel이나 CUDA library를 교체하지 않았다.

[전체 Pod 선언](../../experiments/device-plugin-pytorch/manifests/gpu-pod-no-lt-only.yaml)과
[실행 절차](../../experiments/device-plugin-pytorch/README.md)를 참조한다.
선언의 namespace·node·GID는 시험 VM 값이므로 사용 환경에 맞춰 변경한다.
선택한 이미지·작은 eager FP32 MLP의 검증 결과이며 임의 PyTorch workload의 호환성을 보장하지 않는다.

2026-11-08 [기본 경로 LSTM 실험](../../experiments/rnn-default/results/20261108/REPORT.md)에서는
cuDNN RNN v8·cuBLASLt 중계를 추가한 후보 Guest/Worker로 공식 PyTorch의 LSTM 학습이 통과했다.
cuDNN을 활성화하고 `DISABLE_ADDMM_CUDA_LT`를 설정하지 않은 상태에서 128 step 학습,
CPU 검산, 새 Pod의 체크포인트 재개와 MLP 회귀를 확인했다.
후속 [v0.5.9·Device Plugin v0.1.1 공개 배포물 검증](../../deploy/releases/evidence/v0.5.9/README.md)에서도
기본 경로 LSTM·MLP 학습과 체크포인트 재개가 통과했다. v0.1.1에서는 위 Lt 우회 설정이 필요하지 않다.
이 결과가 CNN 또는 임의 PyTorch workload의 지원을 뜻하지는 않는다.

## 진단과 복구

Plugin binary의 읽기 전용 진단:

```sh
/device-plugin --doctor --broker-gid=YOUR_VMWEAVE_GID \
  --library-sha256=YOUR_GUEST_LIBRARY_SHA256
```

| 상태 | 확인·대응 |
|---|---|
| 자원 없음 | node label, DaemonSet, kubelet 등록 로그, discovery file 존재 확인 |
| 자원 Unhealthy | status 시간·boot ID·library hash·socket GID 확인. 실제 고장 원인을 먼저 조사 |
| Pending | 기존 GPU 자원 할당과 Node 상태 확인. 할당됐다고 quota가 증가하지 않음 |
| 애플리케이션 접속 실패 | workload GID·Guest library·직접 실행 중인 client 확인 |
| Plugin/kubelet 재시작 | 자동 재등록 확인. Broker나 VM을 함께 재시작할 필요 없음 |
| Broker/Worker 장애 | 신규 할당 차단. 기존 Pod의 자동 GPU 이전·무중단 복구는 지원하지 않음 |
| VM 재생성 | 새 binding 확인 후 workload 재생성. 이전 CUDA context를 복구하지 않음 |

상태 정보는 1초 주기로 갱신하며 최근 transport 진행이 10초를 넘으면 신규 할당을 막는다.
이는 실제 GPU 연산 성공을 보장하는 probe가 아니다. 긴 CUDA 요청이나 시계 역행도
보수적으로 Unhealthy를 만들 수 있다. 실행 중인 GPU Pod를 Plugin이 강제 종료하지 않는다.
소켓은 directory 단위로 mount하므로 inode 교체를 볼 수 있지만, 이것이 기존 세션의 복구를 뜻하지 않는다.

## 제거와 업그레이드

GPU workload를 정상 종료한 뒤 `helm uninstall vmweave-device-plugin -n vmweave-device-plugin`을
실행하고 관리자가 추가한 node label을 제거한다. Plugin 제거는 Guest Broker·library·외부 GPU
할당을 제거하지 않는다. 제거 후 필요하면 Guest 직접 smoke로 기존 경로를 확인한다.
Plugin 삭제가 실행 중 Pod의 Broker 접근을 즉시 취소하지도 않는다.

Broker package 업그레이드는 정지 Guest 또는 다음 fresh binding 전에 수행한다.
Plugin·workload의 library hash와 ABI 호환성을 함께 맞춘다.
소스·모의 검증과 실제 VM 검증은 별도로 기록하며, 공개 릴리스의 증거를 확인한 뒤 사용한다.

[개발 계약과 단위 검사](../../integrations/kubernetes-device-plugin/README.md)
