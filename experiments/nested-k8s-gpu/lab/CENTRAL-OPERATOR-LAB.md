# 기존 vmweave-system으로 VM 내부 2노드 Kubernetes·GPU Pod 구성하기

작성일: 2026-10-28 · 상태: **향후 실습 절차 / 이 경로의 VM·GPU 실습은 아직 미실행**

이 실습은 **기존 `vmweave-system`의 controller와 webhook**을 사용한다. 새 Operator나 Webhook을
설치하지 않는다. 이미 관리 중인 workload namespace에 새 VM 두 대를 만들고,
Control Plane 1대와 Worker 1대를 구성한 뒤 Worker의 비특권 Pod에서 VMWeave GPU 연산을 확인한다.

[기존 실험 보고서](../results/20261028-minimal/REPORT.md)는 같은 이미지의 **별도**
`vmweave-nested-system` Operator로 실행한 결과다. [노드 캡처](../results/20261028-nodes-capture/README.md)도
그 환경의 화면이며, 본 중앙 Operator 실습의 성공 증거가 아니다.

## 1. 실행 범위·권한·버전

| 위치 | 수행할 작업 |
|---|---|
| 관리 호스트 | 외부 kubectl, 중앙 Operator 확인, manifest 생성·적용, SSH, 증거 수집 |
| 지정 GPU 노드 | 새 local PV 디렉터리·OS disk 준비, 호스트 GPU PID 확인 |
| 새 CP VM | Kubernetes 설치·init, 내부 kubectl, Cilium 설치 |
| 새 Worker VM | Kubernetes 설치·join, broker 설치, GPU 앱 이미지 빌드 |

아래 예제는 **관리 호스트가 지정 GPU 노드인 경우**, Ubuntu amd64 Guest, 기존 KubeVirt 및
ivshmem 지원 launcher, 일반 HAMi backend를 전제로 한다. 다른 호스트에서 관리한다면 디스크 준비와
`observe_gpu.py`의 호스트 `/proc`·`nvidia-smi` 관측은 해당 GPU 노드에서 수행해야 한다.
PV 생성·Profile 승인은 관리자 작업이다. Guest에는 passwordless sudo 가능한 `ubuntu` 계정을 만든다.

“최신”은 **실습 당일 기존 중앙 controller/webhook에 실제 배포된 버전**이다.
2026-10-28 조회에서는 두 구성요소가 v0.5.5 Operator digest
`bcb3e0accc420164bfb09d4c8851fa3c5f09f0f812b90328eb030c955c9356b2`를 사용했다.
[조회 원본](central-operator-snapshot-20261028.json)과 [읽기 전용 사전 점검 결과](preflight-observed-20261028.json)를 보존했다.
이 점검은 VM 생성이나 GPU 실행을 포함하지 않는다.

실습 당일 다른 이미지가 배포되어 있으면 그 배포와 일치하는 release lock·Guest/Worker/helper/hook을 선택한다.
검증되지 않은 `latest` tag나 과거 artifact를 섞지 않는다. 이 실습을 위해 중앙 Operator를 자동 업그레이드하거나
v0.5.5로 내리지 않는다. 최신 공개 릴리스로의 운영 업그레이드가 필요한 경우에는 먼저 별도의
[업그레이드 절차](../../../docs/guides/upgrade-uninstall.md)를 완료한다.

Kubernetes 설치 조합은 기존 실험에서 확인한 **1.35.9 / CRI-O 1.35.10 / Cilium 1.20.2**를 사용한다.
이는 최신 Kubernetes를 자동 선택한다는 의미가 아니다. 패키지 공급이나 Guest kernel 조건이 달라졌다면
새 조합을 양쪽 VM에 동일하게 고정하고 변경을 기록한다.

## 2. 관리 대상과 실행 경로 확인

저장소 루트의 전용 Bash 세션에서 시작한다. 오류 시 중단하도록 설정한다. 중단 후에는 로그와
완료 상태를 확인하고 필요한 환경 변수·함수를 복원한 뒤 실패 단계부터 재개한다.
아래 값을 실습 환경에 맞게 채운다. 고유 prefix와 출력 경로를 사용한다.

```bash
set -euo pipefail
umask 077
export OUTER_CONTEXT=kubernetes-admin@kubernetes
export LAB_NS=vmweave-test-b
export LAB_NODE=gpu-4
export LAB_PREFIX="central-k8s-$(date +%Y%m%d%H%M)"
export LAB_WORK="$PWD/.local/$LAB_PREFIX"
export LAB_PVROOT="/var/lib/vmweave-labs/$LAB_PREFIX"
export LAB_GPU_UUID='REPLACE_WITH_APPROVED_GPU_UUID'
export RELEASE_LOCK="$PWD/deploy/releases/v0.5.5.json"
export LAB_SOURCE="$PWD/experiments/nested-k8s-gpu"
mkdir -m 700 -p "$LAB_WORK"
mkdir -p "$LAB_WORK/evidence"
# 관리 kubeconfig는 비공개 경로로 복사한다. 원본의 current-context를 바꾸지 않는다.
kubectl --context "$OUTER_CONTEXT" config view --minify --raw --flatten > "$LAB_WORK/outer.kubeconfig"
chmod 600 "$LAB_WORK/outer.kubeconfig"
export KUBECONFIG="$LAB_WORK/outer.kubeconfig"
test "$(kubectl config current-context)" = "$OUTER_CONTEXT"
k() { kubectl --context "$OUTER_CONTEXT" "$@"; }
```

실습 계정의 실제 관리 범위를 확인한다. `vmweave-test-b`는 작성 시점의 예제이며,
실습 당일에도 두 구성요소의 `--namespaces`와 Webhook selector에 포함되어 있어야 한다.

```bash
python3 "$LAB_SOURCE/lab/preflight.py" \
  --context "$OUTER_CONTEXT" --namespace "$LAB_NS" \
  --release-lock "$RELEASE_LOCK" --output "$LAB_WORK/evidence/central-before.json"
k auth can-i update virtualmachines.kubevirt.io -n "$LAB_NS" \
  --as=system:serviceaccount:vmweave-system:vmweave-controller
k auth can-i create pods -n "$LAB_NS" \
  --as=system:serviceaccount:vmweave-system:vmweave-controller
```

preflight는 중앙 Deployment의 active mode·관리 namespace·이미지·Ready Pod·ServiceAccount RoleBinding,
해당 namespace에 적용되는 VMWeave validating webhook의 중앙 Service 연결, 중복 controller 범위를 검사한다.
두 `can-i`는 기본 release 이름 기준으로 `yes`여야 한다. ServiceAccount 이름이 다르면
preflight 결과의 실제 이름을 사용한다. API audit가 있다면 이후 생성 요청의 ServiceAccount까지 함께 보존한다.
이 사전 점검만으로 특정 reconcile 요청의 audit trace를 대신했다고 표현하지 않는다.

**등록되지 않은 새 namespace를 사용하려면:** controller args만 직접 patch하지 않는다.
관리 namespace, RBAC, Webhook selector는 같은 범위여야 한다. 기존 active Channel 회수와 유지보수가
필요한 [관리 범위 변경 절차](../../../docs/guides/upgrade-uninstall.md)를 운영자가 별도로 완료한 후
이 단계부터 시작한다. 기존 실험 namespace를 두 Operator가 동시에 관리하게 하지 않는다.

## 3. 가용 자원과 준비물 확정

새 VM에는 각각 4 vCPU, CP 8 GiB / Worker 16 GiB RAM, root PVC 40 / 80 GiB가 필요하다.
SHM PVC 1 GiB와 launcher·GPU Worker·이미지 저장 공간도 확보한다.

```bash
k get node "$LAB_NODE" -o json > "$LAB_WORK/evidence/outer-node.json"
k get vmi,pods -A -o wide > "$LAB_WORK/evidence/outer-workloads-before.txt"
k get gpuprofiles,gpurequests,sharedmemorychannels -A -o json > "$LAB_WORK/evidence/outer-gpu-before.json"
nvidia-smi --query-gpu=index,uuid,memory.total,memory.used,utilization.gpu --format=csv
ip -4 route
k get servicecidrs -o yaml
```

- GPU UUID, HAMi 예약 compute/VRAM, DRA 또는 기존 업무가 사용하는 GPU를 함께 확인한다.
  **GPU utilization 0만으로 미예약 GPU라고 판단하지 않는다.** 앞선 실험은 quota를 유지하고 있다.
- 본 예제는 새 GPUProfile에 compute 50% / 2048 MiB를 요청한다. 가용하지 않으면 다른 승인 GPU를
  선택하거나 관리자와 예약을 조정한 뒤 진행한다. 기존 VM의 quota를 임의로 해제하지 않는다.
- 예제의 node `10.249.0.0/24`, Pod `10.250.0.0/16`, Service `10.251.0.0/16`은
  기존 모든 host/VM/Pod/Service/VPN 망과 대조한다. 충돌하면 config에서 세 CIDR·Node IP를 함께 바꾼다.
- OS는 Kubernetes나 broker가 설치되지 않은 **오프라인 Ubuntu 22.04 QCOW2 원본**을 준비하고 공급자
  checksum을 확인한다. 이전 VM의 실행 중 root disk를 복제하지 않는다. artifact image는 부팅 OS가 아니다.
- QEMU UID/GID는 배포에 맞춰 확인한다. 본 예제는 기존 환경의 107:107을 사용한다.
- 실습 중 외부 HAMi/DRA/Operator 변경과 겹치지 않도록 작업 시간을 조정하고 시작·종료 상태를 대조한다.

## 4. 새 manifest와 영구 디스크 준비

```bash
ssh-keygen -q -t ed25519 -N '' -f "$LAB_WORK/id_ed25519"
cp "$LAB_SOURCE/lab/config.example.json" "$LAB_WORK/config.json"
python3 - <<'PY'
import json,os,pathlib
p=pathlib.Path(os.environ['LAB_WORK'])/'config.json';c=json.loads(p.read_text())
c.update(prefix=os.environ['LAB_PREFIX'],namespace=os.environ['LAB_NS'],node=os.environ['LAB_NODE'],
         pv_root=os.environ['LAB_PVROOT'],ssh_public_key=str(p.parent/'id_ed25519.pub'),
         release_lock=os.environ['RELEASE_LOCK'],gpu_uuid=os.environ['LAB_GPU_UUID'])
p.write_text(json.dumps(c,indent=2)+'\n')
PY
# 필요하면 지금 config의 CIDR·주소·MTU·quota·QEMU UID/GID를 수정한다.
python3 "$LAB_SOURCE/lab/render.py" --config "$LAB_WORK/config.json" --output "$LAB_WORK/rendered"
export LAB_RENDER="$LAB_WORK/rendered"
export QEMU_UID=$(python3 -c 'import json,os;print(json.load(open(os.environ["LAB_WORK"]+"/config.json"))["qemu_uid"])')
export QEMU_GID=$(python3 -c 'import json,os;print(json.load(open(os.environ["LAB_WORK"]+"/config.json"))["qemu_gid"])')
export CP_VM="$LAB_PREFIX-cp"
export WORKER_VM="$LAB_PREFIX-worker"
export GPU_PROFILE="$LAB_PREFIX-gpu"
export SHM_PVC="$LAB_PREFIX-shm"
export CP_IP=$(python3 -c 'import json,os;print(json.load(open(os.environ["LAB_WORK"]+"/config.json"))["cp_ip"])')
export WORKER_IP=$(python3 -c 'import json,os;print(json.load(open(os.environ["LAB_WORK"]+"/config.json"))["worker_ip"])')
```

`render.py`는 로컬 파일만 만든다. Operator·Namespace·RBAC·Webhook을 생성하는 manifest는 출력하지 않는다.
새 VM은 Halted이며 MAC/firmware UUID도 새로 생성한다. 원본 installer commit은
`25b80e29bf2de6ec2363f052ea26e5c56210eb03`이다. [설치기 수정 diff](../installation/)를 적용한 복사본을
`rendered/`에 만들고 Guest 작업 경로만 `/home/ubuntu/central-lab`로 바꾼다.

**다음 디스크 명령은 지정 GPU 노드에서 실행한다.** UID/GID를 바꿨다면 명령도 맞춘다.

```bash
export OS_BASE=/absolute/path/to/verified-ubuntu-22.04.qcow2
qemu-img info "$OS_BASE"
qemu-img check "$OS_BASE"
sha256sum "$OS_BASE" > "$LAB_WORK/evidence/os-base.sha256"
# 새 전용 경로여야 한다. 이미 있으면 기존 실습인지 확인하고 다른 prefix를 사용한다.
test ! -e "$LAB_PVROOT"
sudo install -d -m 0755 "$LAB_PVROOT"
sudo install -d -o "$QEMU_UID" -g "$QEMU_GID" -m 0775 "$LAB_PVROOT/cp" "$LAB_PVROOT/worker" "$LAB_PVROOT/shm"
sudo qemu-img convert -f qcow2 -O raw "$OS_BASE" "$LAB_PVROOT/cp/disk.img"
sudo qemu-img convert -f qcow2 -O raw "$OS_BASE" "$LAB_PVROOT/worker/disk.img"
sudo qemu-img resize -f raw "$LAB_PVROOT/cp/disk.img" 40G
sudo qemu-img resize -f raw "$LAB_PVROOT/worker/disk.img" 80G
sudo chown "$QEMU_UID:$QEMU_GID" "$LAB_PVROOT/cp/disk.img" "$LAB_PVROOT/worker/disk.img"
sudo chmod 0660 "$LAB_PVROOT/cp/disk.img" "$LAB_PVROOT/worker/disk.img"
```

생성된 파일의 PV 경로·namespace·node affinity·SSH 공개키·root 용량·새 VM 이름을 확인한 뒤
server dry-run으로 API와 admission 검사를 수행한다.

```bash
k apply --dry-run=server -f "$LAB_RENDER/storage.json"
k apply --dry-run=server -f "$LAB_RENDER/vms.json"
k create -f "$LAB_RENDER/storage.json"
k create -f "$LAB_RENDER/vms.json"
k -n "$LAB_NS" get pvc
k -n "$LAB_NS" patch vm "$CP_VM" --type=merge -p '{"spec":{"runStrategy":"Always"}}'
k -n "$LAB_NS" patch vm "$WORKER_VM" --type=merge -p '{"spec":{"runStrategy":"Always"}}'
k -n "$LAB_NS" wait "vmi/$CP_VM" "vmi/$WORKER_VM" --for=condition=Ready --timeout=300s
```

dry-run의 정책 거부와 Webhook 연결/TLS 오류를 구분한다. 정책을 끄고 진행하지 않는다.
PVC는 Bound, 두 VMI는 Running/Ready여야 한다. 지금은 Worker에 GPU Channel이 없는 준비 부팅이다.

## 5. Guest 접속·설치기 공통 단계

```bash
export CP_SSH=$(k -n "$LAB_NS" get svc "$CP_VM" -o jsonpath='{.spec.clusterIP}')
export WORKER_SSH=$(k -n "$LAB_NS" get svc "$WORKER_VM" -o jsonpath='{.spec.clusterIP}')
SSH_OPTS=(-i "$LAB_WORK/id_ed25519" -o StrictHostKeyChecking=accept-new -o "UserKnownHostsFile=$LAB_WORK/known_hosts")
cpvm() { ssh "${SSH_OPTS[@]}" "ubuntu@$CP_SSH" "$@"; }
workervm() { ssh "${SSH_OPTS[@]}" "ubuntu@$WORKER_SSH" "$@"; }
for role in cpvm workervm; do
  "$role" 'hostname; cat /etc/machine-id; sudo cat /sys/class/dmi/id/product_uuid; uname -r; df -h /; ip -4 address'
  "$role" 'test ! -e /etc/kubernetes/admin.conf && test ! -e /var/lib/etcd && mkdir -p ~/central-lab'
done
scp "${SSH_OPTS[@]}" "$LAB_RENDER/k8s-setup.sh" "$LAB_RENDER/init.yaml" "$LAB_RENDER/cilium-values.yaml" "ubuntu@$CP_SSH:central-lab/"
scp "${SSH_OPTS[@]}" "$LAB_RENDER/k8s-worker-setup.sh" "ubuntu@$WORKER_SSH:central-lab/"
```

SSH 가능 시점은 VMI Ready보다 늦을 수 있다. 고유 hostname/machine-id/product UUID와 root 확장도 확인한다.
아래 설치기와 apt 명령은 **새 Guest에서만** 실행한다. 한 단계가 실패하면 로그를 남기고 원인을 수정한 뒤
그 단계부터 재개한다. init/join 완료 상태가 있으면 자동 reset하지 않는다.

```bash
for step in system-prep apt-repos install-packages; do
  cpvm "cd ~/central-lab && sudo env DEBIAN_FRONTEND=noninteractive KUBERNETES_VERSION=v1.35 bash k8s-setup.sh --step $step" \
    > "$LAB_WORK/evidence/cp-$step.log" 2>&1
done
for step in system-prep apt-repos install-packages; do
  workervm "cd ~/central-lab && sudo env DEBIAN_FRONTEND=noninteractive KUBERNETES_VERSION=v1.35 bash k8s-worker-setup.sh --step $step" \
    > "$LAB_WORK/evidence/worker-$step.log" 2>&1
done
```

양쪽 VM의 설치 완료를 확인한 뒤 다음 공통 설정으로 진행한다.

```bash
for role in cpvm workervm; do
  "$role" 'sudo bash -se' <<'SH'
export DEBIAN_FRONTEND=noninteractive
apt-get install -y wireguard-tools podman gcc libc6-dev
install -d /etc/crio/crio.conf.d /etc/systemd/system/kubelet.service.d /root/central-lab-original-cni
printf '[crio.runtime]\ncgroup_manager = "systemd"\n' > /etc/crio/crio.conf.d/99-kubernetes.conf
printf '[Unit]\nAfter=wg-quick@wg0.service\nWants=wg-quick@wg0.service\n' > /etc/systemd/system/kubelet.service.d/20-wireguard.conf
# Cilium 설치 전에 새 Guest의 기본 bridge CNI 설정을 백업한다.
for f in /etc/cni/net.d/*.conf /etc/cni/net.d/*.conflist; do
  [ ! -f "$f" ] || mv "$f" /root/central-lab-original-cni/
done
systemctl daemon-reload
systemctl restart crio
systemctl enable kubelet
umask 077
test ! -e /etc/wireguard/private.key
wg genkey > /etc/wireguard/private.key
wg pubkey < /etc/wireguard/private.key > /etc/wireguard/public.key
dpkg-query -W cri-o kubelet kubeadm kubectl
SH
done
```

## 6. 고유 Node IP와 터널 MTU

두 masquerade Guest의 기본 주소가 `10.0.2.2`로 같아도 그 주소로 join하지 않는다.
기존 실험과 같은 방식으로 각 VM의 ClusterIP Service를 WireGuard peer endpoint로 쓰고
고유 wg0 IP를 Node IP로 고정한다. 키는 Guest 안에서만 읽는다.

```bash
CP_PUB=$(cpvm 'sudo cat /etc/wireguard/public.key')
WORKER_PUB=$(workervm 'sudo cat /etc/wireguard/public.key')
WG_MTU=$(python3 -c 'import json,os;print(json.load(open(os.environ["LAB_WORK"]+"/config.json"))["wireguard_mtu"])')
NODE_PREFIX=$(python3 -c 'import json,os,ipaddress;print(ipaddress.ip_network(json.load(open(os.environ["LAB_WORK"]+"/config.json"))["node_cidr"]).prefixlen)')
configure_wg() {
  local remote=$1 own=$2 peer=$3 public=$4 endpoint=$5
  "$remote" "sudo env OWN='$own/$NODE_PREFIX' PEER='$peer' PUB='$public' ENDPOINT='$endpoint:51820' MTU='$WG_MTU' bash -se" <<'SH'
umask 077
key=$(cat /etc/wireguard/private.key)
cat > /etc/wireguard/wg0.conf <<EOF
[Interface]
Address = $OWN
ListenPort = 51820
MTU = $MTU
PrivateKey = $key
[Peer]
PublicKey = $PUB
AllowedIPs = $PEER/32
Endpoint = $ENDPOINT
PersistentKeepalive = 25
EOF
systemctl enable --now wg-quick@wg0
SH
}
configure_wg cpvm "$CP_IP" "$WORKER_IP" "$WORKER_PUB" "$WORKER_SSH"
configure_wg workervm "$WORKER_IP" "$CP_IP" "$CP_PUB" "$CP_SSH"
cpvm "ping -c 1 '$WORKER_IP'; ping -M do -c 1 -s '$((WG_MTU-28))' '$WORKER_IP'"
workervm "ping -c 1 '$CP_IP'; ping -M do -c 1 -s '$((WG_MTU-28))' '$CP_IP'"
```

기존 환경의 Guest eth0 MTU는 **1280**이었고, WireGuard 1220과 Cilium 기준 1220에서
노드 간 VXLAN route MTU가 **1170**이었다. Cilium `MTU`를 Pod payload 크기와 동일시하지 않는다.
실제 물리/Guest MTU와 터널 오버헤드에 따라 조정하고, 변경하면 wg0·Cilium 설정·시험 payload를 함께 맞춘다.
외부 NIC의 MTU를 이 실습 때문에 바꾸지 않는다.

## 7. broker 설치와 중앙 Operator의 새 GPU binding

호환 release lock에서 이미지를 읽는다. Guest artifact는 일반 사용자 GPU 앱의 native NVIDIA driver 설치를
대신하는 VMWeave 라이브러리 묶음이다. 새 Worker Guest에 broker가 active가 되기 전에 설치한다.

```bash
image_of() { python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["images"][sys.argv[2]])' "$RELEASE_LOCK" "$1"; }
GUEST_IMAGE=$(image_of guest-artifacts)
HELPER_IMAGE=$(image_of helper)
HOOK_IMAGE=$(image_of hook)
scp "${SSH_OPTS[@]}" scripts/operator/export-guest.py "ubuntu@$WORKER_SSH:central-lab/"
workervm "sudo python3 /home/ubuntu/central-lab/export-guest.py --engine podman --image '$GUEST_IMAGE' --output /home/ubuntu/central-lab/guest"
workervm 'sudo sh /home/ubuntu/central-lab/guest/install_guest_broker.sh /home/ubuntu/central-lab/guest && sudo usermod -aG vmweave ubuntu'
k -n "$LAB_NS" patch vm "$WORKER_VM" --type=merge -p '{"spec":{"runStrategy":"Halted"}}'
k -n "$LAB_NS" wait --for=delete "vmi/$WORKER_VM" --timeout=180s
k create -f "$LAB_RENDER/profile.json"
# 관리자가 GPU UUID·가용 quota·노드·digest를 확인한 뒤 승인한다.
k -n "$LAB_NS" patch gpuprofile "$GPU_PROFILE" --type=merge -p '{"spec":{"approved":true}}'
COMPUTE=$(python3 -c 'import json,os;print(json.load(open(os.environ["LAB_WORK"]+"/config.json"))["compute"])')
MEMORY=$(python3 -c 'import json,os;print(json.load(open(os.environ["LAB_WORK"]+"/config.json"))["memory_mib"])')
python3 scripts/operator/create-channel.py --lifecycle VM --namespace "$LAB_NS" \
  --vm "$WORKER_VM" --name "$WORKER_VM" --profile "$GPU_PROFILE" --pvc "$SHM_PVC" \
  --compute "$COMPUTE" --memory "${MEMORY}Mi" --sessions 1 --uid "$QEMU_UID" --gid "$QEMU_GID" \
  --helper-image "$HELPER_IMAGE" --hook-image "$HOOK_IMAGE"
k -n "$LAB_NS" patch vm "$WORKER_VM" --type=merge -p '{"spec":{"runStrategy":"Always"}}'
k -n "$LAB_NS" wait "sharedmemorychannel/$WORKER_VM" --for=jsonpath='{.status.phase}'=Ready --timeout=300s
workervm 'sudo systemctl is-active vmweave-guest-broker; test -S /run/vmweave/gpu.sock; getent group vmweave'
workervm 'env LD_LIBRARY_PATH=/opt/vmweave/lib VMWEAVE_BROKER_SOCKET=/run/vmweave/gpu.sock /opt/vmweave/bin/guest-gpu-smoke 23 2' \
  > "$LAB_WORK/evidence/guest-smoke.log" 2>&1
k -n "$LAB_NS" get sharedmemorychannel "$WORKER_VM" -o json > "$LAB_WORK/evidence/channel-ready.json"
```

`create-channel.py`는 현재 `KUBECONFIG`를 사용하므로 2절의 외부 kubeconfig 분리가 필요하다.
VM/Request/Profile/PVC의 UID는 새 객체에서 조회한다. 과거 `manifests/gpu.json`의 UID/status/allocation을 적용하지 않는다.
CP VM에는 GPU Channel을 만들지 않는다. Channel Ready와 broker active만으로 GPU kernel 성공을 대신하지 않는다.

## 8. Control Plane 초기화와 Worker 조인

관리 호스트에 준비한 고정 버전 Helm 3.22.0과 Cilium CLI 0.20.1을 확인한 뒤 복사한다.
두 도구가 없으면 공식 릴리스에서 해당 버전과 checksum을 확인해 준비한다. 설치기 복사본은 최신 도구를 자동 다운로드하지 않는다.

```bash
helm version --short
cilium version --client
sha256sum /usr/local/bin/helm /usr/local/bin/cilium > "$LAB_WORK/evidence/tools.sha256"
scp "${SSH_OPTS[@]}" /usr/local/bin/helm /usr/local/bin/cilium "ubuntu@$CP_SSH:central-lab/"
cpvm 'cd ~/central-lab && sudo bash k8s-setup.sh --step init-cluster' > "$LAB_WORK/evidence/init.log" 2>&1
cpvm 'cd ~/central-lab && sudo bash k8s-setup.sh --step kubeconfig'
cpvm 'cd ~/central-lab && sudo bash k8s-setup.sh --step install-helm'
cpvm 'kubectl get --raw=/readyz'
```

초기화가 실패하면 `/etc/kubernetes/admin.conf`, `/var/lib/etcd`, API 상태를 확인한다. 성공한 init을 재실행하지 않는다.
복사본은 원 설치기의 `i` 변수 충돌을 `local i`로 수정하고, `--skip-token-print`를 사용한다.
제한 수명의 join token을 비공개 파일로 옮긴다.

```bash
cpvm 'sudo kubeadm token create --ttl 2h --print-join-command' > "$LAB_WORK/join-command.private"
chmod 600 "$LAB_WORK/join-command.private"
python3 - <<'PY'
import json,os,pathlib
p=pathlib.Path(os.environ['LAB_WORK']);c=json.loads((p/'config.json').read_text());a=(p/'join-command.private').read_text().split()
data={'apiVersion':'kubeadm.k8s.io/v1beta4','kind':'JoinConfiguration',
 'discovery':{'bootstrapToken':{'apiServerEndpoint':c['cp_ip']+':6443','token':a[a.index('--token')+1],
 'caCertHashes':[a[a.index('--discovery-token-ca-cert-hash')+1]]}},
 'nodeRegistration':{'name':c['prefix']+'-worker','criSocket':'unix:///var/run/crio/crio.sock',
 'kubeletExtraArgs':[{'name':'node-ip','value':c['worker_ip']}]}}
f=p/'join.yaml';f.write_text(json.dumps(data,indent=2)+'\n');f.chmod(0o600)
PY
scp "${SSH_OPTS[@]}" "$LAB_WORK/join.yaml" "ubuntu@$WORKER_SSH:central-lab/join.yaml"
workervm 'chmod 600 ~/central-lab/join.yaml; cd ~/central-lab && sudo bash k8s-worker-setup.sh --step join-cluster' \
  > "$LAB_WORK/evidence/join.log" 2>&1
# Worker join 후 CNI를 설치한다. CP taint는 유지한다.
cpvm 'cd ~/central-lab && sudo env CILIUM_VERSION=1.20.2 bash k8s-setup.sh --step install-cilium' \
  > "$LAB_WORK/evidence/cilium-install.log" 2>&1
```

CNI 설치 전 NotReady는 중간 상태다. `cilium-values.yaml`에는 WireGuard device, IPv4,
MTU, `ipam.mode=kubernetes`, kube-proxy 유지 및 **직접 CP IP의 k8sServiceHost/Port**가 들어 있다.
이미지 다운로드로 readiness timeout만 발생하면 Helm 설치를 반복하지 않고 다음 상태 확인만 수행한다.

```bash
cpvm 'sudo env KUBECONFIG=/etc/kubernetes/admin.conf cilium status --wait --wait-duration 10m'
cpvm 'kubectl get nodes -o wide; kubectl get pods -n kube-system -o wide'
cpvm 'kubectl get nodes -o json' > "$LAB_WORK/evidence/nodes-ready-1.json"
sleep 30
cpvm 'kubectl get nodes -o json' > "$LAB_WORK/evidence/nodes-ready-2.json"
```

양쪽 Node Ready, 고유 InternalIP, CoreDNS/Cilium Ready, CP control-plane taint 유지를 확인한다.
CoreDNS가 `10.88.*` 같은 이전 bridge IP라면 새 Guest의 기본 CNI 제거 여부를 확인하고 DNS Deployment를 재생성한다.
이미 올바른 Pod CIDR이면 추가 재생성을 하지 않는다. Cilium MTU 변경은 agent 재기동과 기존 Pod 재생성이 필요할 수 있다.

## 9. 노드 간 CPU 통신 검증과 실제 화면 수집

서로 다른 노드에 임시 busybox Pod를 놓고 Worker의 httpd를 조회한다. 다음은 **관리 호스트**에서 YAML을 생성·전달하는 명령이다.
`CPU_IMAGE`는 versioned image를 pull한 뒤 실제 digest로 고정한다.

```bash
workervm 'sudo podman pull docker.io/library/busybox:1.36.1'
export CPU_IMAGE=$(workervm 'sudo podman image inspect docker.io/library/busybox:1.36.1 --format "{{index .RepoDigests 0}}"')
cpvm 'kubectl create namespace lab-validation'
python3 - <<'PY' > "$LAB_WORK/rendered/cpu.json"
import json,os
ns='lab-validation';im=os.environ['CPU_IMAGE'];p=os.environ['LAB_PREFIX'];items=[]
for role in ['cp','worker']:
 spec={'nodeSelector':{'kubernetes.io/hostname':p+'-'+role},'automountServiceAccountToken':False,
 'containers':[{'name':'test','image':im,'securityContext':{'capabilities':{'add':['NET_RAW']}},
 'command':['sh','-ec','mkdir -p /tmp/www; echo central-lab-ok > /tmp/www/index.html; exec httpd -f -p 8080 -h /tmp/www'] if role=='worker' else ['sleep','3600']}]}
 if role=='cp':spec['tolerations']=[{'key':'node-role.kubernetes.io/control-plane','operator':'Exists','effect':'NoSchedule'}]
 if role=='worker':
  items.append({'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':'cpu-web','namespace':ns},'spec':{'replicas':1,'selector':{'matchLabels':{'app':'cpu-web'}},'template':{'metadata':{'labels':{'app':'cpu-web'}},'spec':spec}}})
 else:items.append({'apiVersion':'v1','kind':'Pod','metadata':{'name':'cpu-client','namespace':ns},'spec':spec})
items.append({'apiVersion':'v1','kind':'Service','metadata':{'name':'cpu-web','namespace':ns},'spec':{'selector':{'app':'cpu-web'},'ports':[{'port':80,'targetPort':8080}]}})
print(json.dumps({'apiVersion':'v1','kind':'List','items':items}))
PY
cpvm 'kubectl create -f -' < "$LAB_RENDER/cpu.json"
cpvm 'kubectl -n lab-validation rollout status deploy/cpu-web --timeout=180s; kubectl -n lab-validation wait pod/cpu-client --for=condition=Ready --timeout=180s'
CPU_POD=$(cpvm 'kubectl -n lab-validation get pod -l app=cpu-web -o jsonpath="{.items[0].metadata.name}"')
CPU_IP=$(cpvm "kubectl -n lab-validation get pod '$CPU_POD' -o jsonpath='{.status.podIP}'")
CLIENT_IP=$(cpvm 'kubectl -n lab-validation get pod cpu-client -o jsonpath="{.status.podIP}"')
cpvm "kubectl -n lab-validation exec cpu-client -- wget -qO- http://$CPU_IP:8080"
cpvm 'kubectl -n lab-validation exec cpu-client -- nslookup cpu-web.lab-validation.svc.cluster.local'
cpvm 'kubectl -n lab-validation exec cpu-client -- wget -qO- http://cpu-web'
cpvm "kubectl -n lab-validation exec cpu-client -- ping -c 1 -s '$((WG_MTU-50-28))' '$CPU_IP'"
cpvm "kubectl -n lab-validation exec '$CPU_POD' -- ping -c 1 '$CLIENT_IP'"
cpvm "kubectl -n lab-validation get pod '$CPU_POD' -o json" > "$LAB_WORK/evidence/cpu-before.json"
cpvm "kubectl -n lab-validation delete pod '$CPU_POD' --wait=true; kubectl -n lab-validation rollout status deploy/cpu-web --timeout=120s"
cpvm 'kubectl -n lab-validation get pod -l app=cpu-web -o json' > "$LAB_WORK/evidence/cpu-after.json"
```

HTTP 응답 `central-lab-ok`, DNS/Service 성공, MTU 경계와 역방향 ICMP 성공,
삭제된 Pod와 대체 Pod의 서로 다른 UID 및 Ready를 확인한다. `NET_RAW`는 CPU ICMP 검사에만 사용한다.

캡처는 CP VM의 실제 SSH 터미널에서 다음 순서로 실행한다. 같은 화면에 hostname·context·실제 조회 시각을 남긴다.
캡처 후 `exit`로 관리 호스트에 돌아와 다음 단계를 실행한다.

```bash
# 관리 호스트에서 접속
ssh "${SSH_OPTS[@]}" "ubuntu@$CP_SSH"
# 여기부터 CP VM 터미널
date --iso-8601=seconds
hostname
kubectl config current-context
kubectl get nodes -o wide
```

두 Node의 Ready와 고유 IP가 보이는 원본 PNG 및 명령 출력, 시각/timezone, VM/VMI UID를 저장한다.
Worker의 ROLES `<none>` 표시는 역할 label이 없는 경우의 표시이며 미가입을 뜻하지 않는다.
기존 캡처 파일이나 과거 `results/.../capture.cjs`는 기존 VM/키에 고정돼 있으므로 새 실습에 그대로 실행하지 않는다.

## 10. GPU 앱 이미지와 Pod A/B

다음 명령은 다시 **관리 호스트**에서 실행한다. 기존 correctness 프로그램을 새 Guest 라이브러리와 링크한다.
Pod 내부에 GPU Device Plugin, GPU Extended Resource 선언, Node allocatable patch는 만들지 않는다.

```bash
workervm 'mkdir -p ~/central-lab/workload'
scp "${SSH_OPTS[@]}" "$LAB_SOURCE/workloads/correctness.c" "$LAB_SOURCE/workloads/Containerfile" "ubuntu@$WORKER_SSH:central-lab/workload/"
workervm "cd ~/central-lab/workload && cp /opt/vmweave/lib/libvmweave_guest.so . && gcc -std=c11 -O2 -Wall -Wextra -Werror correctness.c -L. -lvmweave_guest -o correctness && sudo podman build --pull=false -t localhost/central-gpu:$LAB_PREFIX -f Containerfile ."
export GPU_IMAGE=$(workervm "sudo podman image inspect localhost/central-gpu:$LAB_PREFIX --format '{{index .RepoDigests 0}}'")
export GPU_GID=$(workervm 'getent group vmweave | cut -d: -f3')
workervm "sudo podman image inspect localhost/central-gpu:$LAB_PREFIX" > "$LAB_WORK/evidence/workload-image.json"
```

다음 함수는 Job manifest를 로컬 생성한다. `gpu-no-socket no` 인자는 소켓 없는 대조용이다.

```bash
gpu_manifest() {
  python3 - "$1" "${2:-yes}" <<'PY'
import json,os,sys
name,socket=sys.argv[1:];c={'name':'gpu','image':os.environ['GPU_IMAGE'],'imagePullPolicy':'Never',
 'env':[{'name':'VMWEAVE_BROKER_SOCKET','value':'/run/vmweave/gpu.sock'},{'name':'LD_LIBRARY_PATH','value':'/opt/vmweave/lib'}],
 'securityContext':{'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}},
 'resources':{'requests':{'cpu':'100m','memory':'128Mi'},'limits':{'cpu':'1','memory':'512Mi'}}}
s={'restartPolicy':'Never','automountServiceAccountToken':False,'nodeSelector':{'kubernetes.io/hostname':os.environ['WORKER_VM']},
 'securityContext':{'runAsNonRoot':True,'runAsUser':1000,'runAsGroup':int(os.environ['GPU_GID']),'seccompProfile':{'type':'RuntimeDefault'}},'containers':[c]}
if socket=='yes':
 c['volumeMounts']=[{'name':'broker','mountPath':'/run/vmweave','readOnly':True}]
 s['volumes']=[{'name':'broker','hostPath':{'path':'/run/vmweave','type':'Directory'}}]
print(json.dumps({'apiVersion':'batch/v1','kind':'Job','metadata':{'name':name,'namespace':'lab-validation'},
 'spec':{'backoffLimit':0,'activeDeadlineSeconds':360,'template':{'spec':s}}},indent=2))
PY
}
observe() {
  python3 "$LAB_SOURCE/lab/observe_gpu.py" --context "$OUTER_CONTEXT" --namespace "$LAB_NS" \
    --vm "$WORKER_VM" --gpu-uuid "$LAB_GPU_UUID" --expect "$1" --timeout 60 \
    --output "$LAB_WORK/evidence/$2.json"
}
gpu_once() (
  set -e
  name=$1
  observe idle "$name-before"
  gpu_manifest "$name" > "$LAB_RENDER/$name.json"
  cpvm 'kubectl create -f -' < "$LAB_RENDER/$name.json"
  ready=false
  for i in $(seq 1 120); do
    cpvm "kubectl -n lab-validation logs job/$name" > "$LAB_WORK/evidence/$name-start.log" 2>/dev/null || true
    if grep -q READY_FOR_OBSERVATION "$LAB_WORK/evidence/$name-start.log"; then ready=true; break; fi
    sleep 1
  done
  test "$ready" = true
  pod=$(cpvm "kubectl -n lab-validation get pods -l job-name=$name -o jsonpath='{.items[0].metadata.name}'")
  cpvm "kubectl -n lab-validation get pod '$pod' -o json" > "$LAB_WORK/evidence/$name-pod-start.json"
  observe active "$name-active"
  cpvm "kubectl -n lab-validation exec '$pod' -- touch /tmp/run"
  cpvm "kubectl -n lab-validation wait job/$name --for=condition=Complete --timeout=120s"
  cpvm "kubectl -n lab-validation logs '$pod'" > "$LAB_WORK/evidence/$name-result.log"
  cpvm "kubectl -n lab-validation get pod '$pod' -o json" > "$LAB_WORK/evidence/$name-pod-final.json"
  observe idle "$name-reclaimed"
  python3 - "$LAB_WORK/evidence/$name-result.log" <<'PY'
import json,sys
r=[json.loads(x) for x in open(sys.argv[1]) if x.startswith('{')]
x=next(x for x in r if x.get('event')=='RESULT')
assert x['elements']==8388608 and x['mismatches']==0 and x['checksum']==18014393673449472 and x['kernel_launches']==1
print('PASS: 32 MiB, 8388608 integers, mismatches=0, kernel launches=1')
PY
)
gpu_once gpu-a && gpu_once gpu-b
```

각 Pod는 GPU context·버퍼를 만든 후 `READY_FOR_OBSERVATION`에서 기다린다. 이때 외부 Worker의 CUDA 자식과
호스트 GPU PID를 수집하고 `/tmp/run`으로 해제한다. GPU 이용률만으로 연산을 입증하지 않는다.
`observe_gpu.py`는 지정 GPU 노드에서 NSpid·cgroup·Worker UID를 대조한다. `/proc` 권한 문제는 성공으로 무시하지 않는다.
A/B의 서로 다른 Pod UID, 각각 결과 일치, A 회수 후 B 제출을 확인한다. client별 broker epoch 값은 이 도구가 수집하지 않는다.

## 11. 소켓 없는 대조와 판정

```bash
observe idle no-socket-before
gpu_manifest gpu-no-socket no > "$LAB_RENDER/gpu-no-socket.json"
cpvm 'kubectl create -f -' < "$LAB_RENDER/gpu-no-socket.json"
cpvm 'kubectl -n lab-validation wait job/gpu-no-socket --for=condition=Failed --timeout=120s'
cpvm 'kubectl -n lab-validation logs job/gpu-no-socket' > "$LAB_WORK/evidence/gpu-no-socket.log"
cpvm 'kubectl -n lab-validation get pod -l job-name=gpu-no-socket -o json' > "$LAB_WORK/evidence/gpu-no-socket-pod.json"
observe idle no-socket-after
```

단순한 Failed만으로 합격시키지 않는다. **동일 이미지가 실행된 뒤 GPU API 접근 실패로 종료**했는지,
이미지 pull 실패·잘못된 명령·CPU OOM이 아닌지 확인한다. 다음 체크리스트를 새 실습 보고서에 기록한다.

- 중앙 controller/webhook의 namespace·Pod UID·imageID, 실제 관리 범위와 admission 연결 근거.
- VM/VMI UID, 내부 Node UID, root PVC, IP·CIDR·MTU, release/source·파일 hash.
- 두 Node Ready 2회, CPU Pod 통신·DNS·Service·MTU·재생성 성공.
- Guest smoke 1회, GPU A/B 각 1회 결과·host GPU PID 대응·순차 회수.
- 소켓 없는 대조 실패와 최종 활성 CUDA 자식 0.
- 각 컨테이너 `finishedAt`과 회수 관측 UTC를 함께 남겨 60초 이내인지 계산. 수동 관측 지연은 별도로 표시.
- 종료 시 preflight를 **다른 output 파일**로 다시 실행하고 중앙 Operator의 generation·Pod UID·imageID를 비교.
  HAMi/DRA/다른 서비스의 재배포가 겹쳤다면 환경 불변·장애 인과분리를 주장하지 않는다.

기본 실습은 이 지점에서 완료한다. GPU 자원 사용 순서는 운영자/runner가 관리하며 내부 Kubernetes의 GPU 스케줄링을 검증한 것은 아니다.
24시간 유지나 성능 반복 측정은 포함하지 않는다. 과거 실험의 [운영 조건표](../PLAN.md)는 확장 검증을 원할 때
별도 실행 ID로 적용한다. 이 문서에서 운영·장애 조건까지 이미 중앙 Operator로 통과했다고 기록하지 않는다.

## 12. 수동 복구·종료·철거

GPU 오류가 나면 신규 제출을 멈추고 Pod 로그·exit code·Channel·CUDA 프로세스를 보존한다.
broker service만 restart하여 기존 SHM ring을 재사용하지 않는다. 새 Worker VM에 한해 다음 수동 복구를 수행한다.

```bash
k -n "$LAB_NS" patch vm "$WORKER_VM" --type=merge -p '{"spec":{"runStrategy":"Halted"}}'
k -n "$LAB_NS" wait --for=delete "vmi/$WORKER_VM" --timeout=180s
k -n "$LAB_NS" wait "sharedmemorychannel/$WORKER_VM" --for=jsonpath='{.status.phase}'=Stopped --timeout=180s
k -n "$LAB_NS" get sharedmemorychannel "$WORKER_VM" -o json > "$LAB_WORK/evidence/channel-stopped.json"
k -n "$LAB_NS" patch vm "$WORKER_VM" --type=merge -p '{"spec":{"runStrategy":"Always"}}'
k -n "$LAB_NS" wait "sharedmemorychannel/$WORKER_VM" --for=jsonpath='{.status.phase}'=Ready --timeout=300s
workervm 'sudo systemctl is-active vmweave-guest-broker kubelet crio; cat /proc/sys/kernel/random/boot_id'
cpvm 'kubectl get nodes -o wide; kubectl get nodes -o json'
```

새 VMI/allocation/generation/GPU Worker, 보존된 Node UID/CA/root 상태, 새 boot ID 반영을 확인한 뒤
새 이름의 GPU Job으로 복구를 확인한다. 이전 프로세스 회수를 입증하지 못하면 다음 작업을 제출하지 않는다.
CP 중단은 API 중단을 수반한다. 공유 Operator 재시작·GPU reset·다른 VM 변경은 이 복구에 포함하지 않는다.

성공 후 계속 검토하려면 VM·클러스터·Channel을 유지하되 CPU 시험 Deployment/Pod와 GPU 부하를 종료한다.
Job은 Completed/의도한 Failed 증거로 남길 수 있다. GPU quota 예약이 계속 유지됨을 인계한다.

철거는 증거·필요한 etcd/root 데이터를 보존한 뒤 **새 prefix의 리소스만** 대상으로 한다.
Worker Halted와 Channel Stopped/RuntimeReclaimed, 기존 Worker 제거·backing 회수를 확인한 후
Channel을 정상 삭제하고 삭제 완료를 기다린다. 계약상 추가 drain이 필요한 버전이면 해당 릴리스 절차를 따른다.
이어 새 Request·VM·PVC·Profile·Service·전용 PV를 정리한다. CP도 Halted/VMI 제거 후 정리한다.
Retain PV 파일은 비사용 확인 후 관리자가 별도로 삭제한다.
**기존 workload namespace나 `vmweave-system`, 중앙 Helm release를 삭제하지 않는다.** finalizer를 강제 제거하지 않는다.

증거 공개 전 SSH/WireGuard private key, join token, kubeconfig, Secret 원문을 제외하고 hash 목록을 만든다.
`$LAB_WORK` 전체를 Git에 넣지 않는다. 새 실습 보고서·선별 증거·캡처는 새 results 디렉터리에 보관한다.

## 검증 범위

이 문서 작성에서는 중앙 Operator 사전 점검을 읽기 전용으로 실행했고, manifest 생성과 설치기 구문을
오프라인 검증했다. 기존 중앙 Operator를 사용하는 새 VM 생성·Kubernetes 설치·GPU 시험·장애 주입은 실행하지 않았다.
현재 공개된 PASS 결과와 스크린샷은 모두 별도 Operator를 사용한 2026-10-28 실험에 해당한다.
