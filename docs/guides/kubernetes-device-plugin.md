# VM 내부 Kubernetes Device Plugin

VMWeave Guest의 기존 GPU quota를 내부 Kubernetes에서 예약하고 연결하는 선택 설치 기능이다.
자원은 `vmweave.io/gpu: 1`, 지원 범위는 **할당 컨테이너당 동시 CUDA client 1개**다.
이 값은 물리 GPU 1개나 추가 VRAM 할당을 의미하지 않는다.

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
`command: ["/opt/vmweave/bin/sgemm"]`으로 실행한다.

자원이 하나뿐인 시험 클러스터에서는 A가 할당받은 동안 B는 Pending이다.
A의 CUDA 작업만 끝나고 컨테이너가 계속 실행 중이면 자원은 계속 할당된 상태다.
컨테이너 종료와 Kubernetes 자원 반환, Broker CUDA 세션 회수를 각각 확인한다.

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
