# 다른 클러스터에 배포

한국어 | [English](portable-deployment.en.md)

이 절차의 목표는 PyTorch 없이 VM에서 작은 CUDA 프로그램을 실행하고 회수하는 것입니다.
Kubernetes·KubeVirt·NVIDIA 드라이버·컨테이너 런타임은 관리자가 준비합니다.
별도 시스템에서의 신규 GPU 설치 검증은 아직 NOT_RUN입니다. 아래 지원 기준은
기존 연구 환경과 빌드 대상을 바탕으로 하며 모든 버전 조합의 지원 선언이 아닙니다.

[로컬 패키지 검증 결과와 미실행 범위](../development/portable-deployment-validation.md)를 확인하세요.

## 배포 계약

| 구성 | 기준 |
|---|---|
| 아키텍처 | Linux amd64 |
| 기존 실제 검증 조합 | Kubernetes v1.37.0, KubeVirt v1.9.0 |
| Hook shim | KubeVirt v1.9.0, `versions.lock.yaml`의 digest |
| CUDA / Guest OS | CUDA 12.8.1·cuDNN 9 / Ubuntu 22.04 |
| HAMi | v2.10.0 + 이 저장소의 수정 라이브러리 |
| GPU 실행 | VM과 Worker가 같은 GPU 노드, local filesystem backing |
| 공개 v0.5.2 제약 | VM별 동시 활성 프로그램 1개, 단일 CUDA 복사 16MiB ([큰 복사 구현 후보](../runtime/large-copies.md)) |

운영자가 GPU 노드별 Profile과 local PV를 준비합니다. 시스템 차트는 호스트 디렉터리를
만들거나 드라이버·KubeVirt·HAMi를 자동 교체하지 않습니다. 기본 GPU smoke의 PTX는
sm_70을 사용하므로 대상 GPU·드라이버에서 이 PTX를 지원하는지 실제 smoke로 확인합니다.

## 1. 릴리스 산출물 확보

게시된 최신 버전: [v0.5.2 산출물·다운로드·검증 기록](release-v0.5.2.md).
이전 버전: [v0.3.0](release-v0.3.0.md).

공개 이미지 7종과 digest는 [v0.5.2 release lock](../../deploy/releases/v0.5.2.json)에 있습니다.
일반 HAMi는 `vmweave-hami`, DRA는 `vmweave-hami-dra`를 사용합니다.
나머지 Operator·Helper·Worker·Hook·Guest artifacts는 공통입니다.
과거 Flyt `v1.0.0` 이미지를 현재 배포판으로 사용하지 않습니다.

전용 작업 디렉터리에 릴리스 소스를 확보합니다. 아래 설치 도구와 CRD는 이 소스에서 실행합니다.

```sh
git clone --branch v0.5.2 --depth 1 https://github.com/WoogiBoogi1129/VMWeave-GPU.git vmweave-v0.5.2
cd vmweave-v0.5.2
mkdir -p .local
helm pull oci://ghcr.io/woogiboogi1129/charts/vmweave-operator --version 0.5.1 --destination .local
python3 scripts/operator/release-manifest.py \
  --repository ghcr.io/woogiboogi1129 --tag v0.5.2 \
  --source-revision b9767652292179bef82f47be20b633a205d19824 \
  --include-dra --output .local/release-images.json
```

이미지와 차트는 로그인 없이 조회·다운로드할 수 있습니다. lock 생성 도구는
7종 이미지의 revision label을 확인하지만 암호학적 provenance를 검증하지는 않습니다.
릴리스 기록과 digest 고정 values 파일은 태그 게시 후 main에 추가되었으므로
위 링크에서 확인합니다. 태그 checkout에는 이 파일들이 없으며, 다음 단계에서는
태그에 포함된 일반 values 예제와 생성한 `.local/release-images.json`을 사용합니다.

## 2. 기반 환경과 namespace 준비

- KubeVirt sidecar hook 설정과 ivshmem 지원 QEMU를 확인합니다.
- **일반 HAMi 선택 시:** [HAMi 수정 이미지 절차](../../runtime/hami/README.md)에 따라 신규 설치하거나 기존 HAMi에 overlay를 적용합니다.
  신규 설치는 기존 HAMi chart v2.10.0의 클러스터별 values와 이 저장소의 overlay를 함께 사용합니다.
  기존 release에 `--reuse-values`를 적용하는 명령을 신규 설치에 그대로 쓰지 않습니다.
- **DRA 선택 시:** [DRA 설치 절차](hami-dra.md)에 따라 Driver·DeviceClass·CDI를 준비합니다.
  일반 HAMi scheduler/device-plugin은 DRA 전용 GPU에 필수가 아닙니다. 두 방식을 함께 쓰면 GPU UUID를 분리합니다.
- GPU UUID, runtimeClass와 선택한 backend의 scheduler 이름을 확인합니다.
- namespace를 준비하고 필요한 registry Secret을 각 namespace에 배치합니다.

```sh
kubectl create namespace vmweave-system
kubectl create namespace team-a
python3 scripts/operator/preflight.py --namespace team-a --node YOUR_GPU_NODE \
  --runtime-class nvidia --output .local/preflight.json
```

위 preflight는 일반 HAMi용입니다. DRA는 명령에
`--backend hami-dra --device-class vmweave-hami-dra --gpu-uuid YOUR_GPU_UUID`를 추가합니다.

이 도구는 클러스터를 변경하지 않습니다. `API_CHECKS_PASS`는 API 조회 항목의 성공이며,
출력의 `unverified` 항목을 포함한 호스트 권한·드라이버·이미지 pull·GPU 동작은 별도 확인합니다.
cert-manager를 사용하면 `--tls-mode certManager`를 추가합니다.

## 3. values와 인증서

[기존 Secret 예제](../../deploy/examples/portable/values.json) 또는
[cert-manager 예제](../../deploy/examples/portable/cert-manager-values.json)를
`.local/portable-values.json`으로 복사하고 Operator repository/digest와 namespace를 입력합니다.

`imagePullSecrets`는 시스템 namespace의 Operator용입니다.
`workloads.imagePullSecrets`는 각 workload namespace의 Worker·prepare/reclaim Helper용입니다.
Hook은 KubeVirt launcher에서 실행되므로 사용자 VM의 `spec.template.spec.imagePullSecrets`에
Guest/Hook registry Secret을 지정해야 합니다. 다른 namespace의 Secret은 공유되지 않습니다.

### 기존 Secret

개발 환경은 다음 도구를 사용할 수 있습니다. 운영 인증서는 조직 CA를 사용합니다.
release 이름과 namespace를 바꾸면 인증서 DNS도 바꿔야 합니다.

```sh
python3 scripts/operator/tls.py --release vmweave --namespace vmweave-system \
  --output .local/portable-tls
kubectl -n vmweave-system create secret tls vmweave-webhook-tls \
  --cert=.local/portable-tls/tls.crt --key=.local/portable-tls/tls.key
python3 scripts/operator/install.py --release vmweave --namespace vmweave-system \
  --values .local/portable-values.json --ca .local/portable-tls/ca.crt
```

CA 변경 시 Secret과 Webhook caBundle의 신뢰 전환 순서를 관리자가 조정해야 합니다.
단순 서버 인증서 교체는 controller-runtime의 파일 감시로 반영되는 구조입니다.
실제 갱신 중 admission 연속성은 새 환경 검증 항목이며 자동으로 보장하지 않습니다.

### cert-manager

cert-manager와 cainjector 및 사용 가능한 CA Issuer/ClusterIssuer가 미리 필요합니다.
예제의 issuerRef를 실제 issuer로 바꿉니다. 같은 이름의 TLS Secret을 기존 수동 인증서와
동시에 관리하지 않습니다.

```sh
python3 scripts/operator/install.py --release vmweave --namespace vmweave-system \
  --values .local/portable-values.json
```

차트가 Certificate를 생성하고 cainjector가 CA를 Webhook에 주입합니다.
설치 도구는 CRD 서버 검증·적용 → Webhook 미등록 상태의 Helm 설치 → 등록 순서로 실행합니다.
Certificate Ready와 CA 주입을 기다립니다. scope/mode 변경은 별도 유지보수 절차입니다.

직접 Helm을 사용하는 관리자는 같은 순서를 유지합니다. 최초 설치의 CRD는 Helm의
`crds/`로 설치할 수 있지만 **Helm upgrade가 CRD를 자동 갱신하지는 않습니다**.
cert-manager 사용 예시는 아래와 같습니다. 기존 Secret 방식은 values에 caBundle도 넣습니다.

```sh
helm upgrade --install vmweave charts/vmweave-operator -n vmweave-system \
  -f .local/portable-values.json --set webhook.registrationEnabled=false --wait --timeout 5m
helm upgrade vmweave charts/vmweave-operator -n vmweave-system \
  -f .local/portable-values.json --set webhook.registrationEnabled=true --wait --timeout 5m
kubectl -n vmweave-system wait certificate/vmweave-webhook --for=condition=Ready --timeout=180s
```

두 단계 직접 Helm 예시는 신규 설치에만 사용합니다. 기존 운영 release의 admission을
임의로 비활성화하지 않습니다. 설치 후 `ValidatingWebhookConfiguration`의 caBundle과
관련 CR의 server-side dry-run까지 확인한 뒤 사용자 작업을 허용합니다.

## 4. GPU 노드와 VM 준비

[첫 VM](first-vm.md)의 관리자·사용자 예제를 복사합니다.

- nodeName, GPU UUID, Worker digest, runtimeClass와 schedulerName을 입력합니다.
- 일반 HAMi는 `backend: hami`(생략 시 기본값)와 HAMi scheduler를 사용합니다.
  DRA는 `backend: hami-dra`, `draDeviceClass: vmweave-hami-dra`,
  `schedulerName: default-scheduler`를 지정합니다. 전체 설정은 [DRA 가이드](hami-dra.md)를 따릅니다.
- local PV directory는 관리자가 생성하고 실제 QEMU UID/GID에 맞춥니다.
- Channel 생성의 `--uid`/`--gid`도 같은 값으로 지정합니다. 기본 107:107은 연구 환경 값입니다.
- PV 용량, 디스크 여유, namespace의 Pod 보안 정책과 node taint/toleration을 확인합니다.
- Guest OS root disk와 SHM backing PVC는 별도입니다.
- Guest OS는 영구 root PVC를 권장합니다. containerDisk라면 broker를 이미지에 미리 설치합니다.

Profile 승인과 PV 생성은 관리자 권한으로 수행하며 사용자에게 Profile 승인 권한을 주지 않습니다.
다른 노드를 추가할 때는 각 노드의 Profile·PV를 별도로 만듭니다.

## 5. Guest 런타임 설치

Guest artifacts 이미지는 부팅용 OS가 아닙니다. 관리 호스트에서 추출해 VM으로 전달합니다.
다음 명령의 image는 release lock의 `guest-artifacts` digest 참조입니다.

```sh
python3 scripts/operator/export-guest.py --engine docker \
  --image "$GUEST_ARTIFACTS_IMAGE" --output .local/portable-guest
```

Guest의 Ubuntu 22.04에는 Python 3, systemd, coreutils, util-linux, groupadd가 필요합니다.
아직 GPU 채널을 연결하지 않은 VM에서 artifacts를 복사한 후 실행합니다.

```sh
sudo sh artifacts/install_guest_broker.sh artifacts
sudo usermod -aG vmweave ubuntu
```

설치기는 SHA256SUMS를 확인하며 실행 중 broker 교체를 거부합니다. 새 버전 업그레이드도
활성 세션을 종료하고 새 부팅에서 사용하도록 진행합니다. source revision은
`/opt/vmweave/source-revision.txt`에 기록합니다. 체크섬은 이미지 내부 무결성 검사이며 서명을 대신하지 않습니다.

VM을 Halted로 만든 후 [VM lifecycle 절차](first-vm.md)에 따라 같은 이름의 Channel을 생성합니다.
새 부팅에서 bootstrap이 config drive의 layout을 읽습니다. 사용자 재로그인 후:

```sh
VMWEAVE_BROKER_SOCKET=/run/vmweave/gpu.sock LD_LIBRARY_PATH=/opt/vmweave/lib \
  /opt/vmweave/bin/guest-gpu-smoke 23 2
```

이 프로그램은 GPU 메모리 복사·PTX 커널 결과를 검사합니다. PyTorch는 필요하지 않습니다.

## 6. 설치 검증과 회수

실행 호스트에서 VM Pod IP로 SSH가 가능해야 합니다. 직접 라우팅이 없으면
아래 smoke 명령에 `--virtctl /path/to/virtctl`을 추가해 KubeVirt 터널을 사용합니다. 비밀키는 결과에 저장하지 않습니다.
현재 자동 smoke의 Guest 계정은 `ubuntu`입니다. 전용 시험 VM의 Channel이 Ready인 상태에서:

```sh
python3 scripts/operator/smoke-vm.py --namespace team-a --vm gpu-vm \
  --key YOUR_SSH_KEY --output .local/portable-smoke
```

기본 동작은 GPU 프로그램을 순차 2회 실행하며 VM은 계속 켜 둡니다.
전용 시험 VM에서 재시작과 종료도 검증하려면 `--cycle-disposable-vm`을 추가합니다.
이 경우 기존 프로그램을 중단할 수 있으며, 성공 시 VM을 최종 Halted로 둡니다.
VM/Channel UID, 새 allocation, 이전 Worker 제거를 확인합니다. 실패 시 상태를 기록하고
강제 삭제하지 않습니다. Channel Stopped와 Worker 제거만으로 호스트 파일 삭제까지 독립
검증한 것은 아니므로 관리자도 backing directory 회수를 확인해야 합니다.

## 7. 업그레이드·롤백·제거

[기존 유지보수 절차](../guides/upgrade-uninstall.md)를 따릅니다.

1. 이전 values·이미지 digest·CRD·Profile·사용자 리소스를 백업합니다. 비밀키는 별도 보호합니다.
2. 활성 세션을 종료하고 VM Halted, Channel Stopped 또는 Released와 Worker 회수를 확인합니다.
3. 새 CRD는 server-side dry-run 후 별도 적용합니다. 저장된 객체와 호환되지 않으면 중단합니다.
4. Helm과 Profile/Channel 이미지 참조, Guest artifacts를 호환 릴리스로 함께 갱신합니다.
5. 새 allocation으로 smoke를 실행한 뒤 사용자 작업을 재개합니다.

Helm rollback은 CRD·사용자 Profile·Guest 파일을 되돌리지 않습니다. 이전 runtime/CRD와
호환되는 경우에만 이들을 함께 복원합니다. 수정 HAMi 교체·롤백은 라이브러리의 atomic
교체 절차를 따릅니다. 실행 중 Worker의 매핑 파일을 덮어쓰지 않습니다.

삭제는 사용자 채널 정상 회수·제거 후 Helm release를 제거합니다. 사용자 VM, PVC/PV,
Guest OS 데이터, Helm crds/의 CRD는 자동으로 안전하게 모두 제거되는 것으로 가정하지 않습니다.
남은 사용자 자원을 점검한 후 관리자가 별도 처리합니다. 회수 증거 없이 finalizer를 제거하지 않습니다.

## 완료 판정

다른 시스템에서 공개/승인된 이미지와 이 문서만으로 신규 설치, GPU smoke, VM 재시작,
회수, 인증서 갱신, 업그레이드·제거를 실행하고 결과를 보존해야 타 시스템 배포 검증 완료입니다.
현재 코드·패키지 검증과 이 실제 클러스터 검증은 구분합니다.

HAMi DRA 환경은 [DRA 백엔드 설치와 수명 관리](hami-dra.md)를 참고하세요. 기존 방식과 GPU 할당 대상을 분리해야 합니다.
