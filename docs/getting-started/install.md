# 중앙 VMWeave Operator 설치

관리자용 절차입니다. Go Controller와 Webhook은 `vmweave-system`에 한 번 설치합니다.
사용자 namespace에는 Controller를 설치하지 않습니다. 새 API는 `vmweave.io/v1alpha1`입니다.

## 준비

[사전 조건](prerequisites.md)을 확인하고 저장소 루트에서 실행합니다.
Operator 이미지와 helper/Worker/hook 이미지는 각각 준비합니다. Operator 이미지만 바꾸어
구 Worker를 새 API에서 사용할 수는 없습니다. 현재 실행 보조 도구 일부는 Python입니다.

```sh
cd operator
make build
cd ..
# 일반 빌드 환경에서 images/vmweave/Operator.Containerfile로 빌드·배포하고 digest를 확보합니다.
kubectl create namespace vmweave-system
kubectl create namespace team-a
kubectl create namespace team-b
python3 scripts/operator/tls.py --output .local/vmweave-tls
kubectl -n vmweave-system create secret tls vmweave-webhook-tls \
  --cert=.local/vmweave-tls/tls.crt --key=.local/vmweave-tls/tls.key
```

개발용 CA는 365일, 서버 인증서는 90일입니다. 운영에서는 조직의 인증서 발급 절차를 사용하고
Service DNS `vmweave-webhook.vmweave-system.svc`를 포함합니다. cert-manager 자동 설치는 제공하지 않습니다.

## 이미지 빌드

배포 registry에 올린 뒤 얻은 digest를 설정합니다. 다음은 태그 빌드 예시입니다.
Guest/Worker의 C ABI와 KubeVirt shim 버전을 함께 고정합니다.

```sh
docker build -f images/vmweave/Operator.Containerfile -t YOUR_REGISTRY/vmweave-operator:VERSION .
docker build -f images/vmweave/Helper.Containerfile -t YOUR_REGISTRY/vmweave-helper:VERSION .
docker build -f images/vmweave/Runtime.Containerfile --target worker -t YOUR_REGISTRY/vmweave-worker:VERSION .
docker build -f images/vmweave/Hook.Containerfile \
  --build-arg KUBEVIRT_SHIM_IMAGE=YOUR_DIGEST_PINNED_SHIM \
  -t YOUR_REGISTRY/vmweave-hook:VERSION .
```

CPU 환경은 Operator/helper/hook 빌드가 가능하며 Worker 빌드에는 CUDA 개발 image가 필요합니다.
`build-image.py`는 이미 검증한 로컬 OCI base를 사용하는 실험 노드용 대안입니다.
노드 import는 단일 노드 캐시 배포이며 다중 노드 registry 배포를 대신하지 않습니다.

Guest OS 이미지와 smoke 프로그램은 [Guest 준비](guest-images.md)를 따릅니다.

## 설정과 설치

`deploy/examples/vmweave/active.json`을 복사하고 실제 이미지 repository/digest 및 관리 목록을
입력합니다. 존재하는 namespace만 등록합니다. 새 설치에서 구 active 제어기가 같은 namespace를
관리하고 있으면 설치 도구가 거부합니다. [이전 절차](../guides/migrate-to-vmweave-api.md)를 따릅니다.

```sh
python3 scripts/operator/install.py --values .local/vmweave-values.json \
  --ca .local/vmweave-tls/ca.crt
kubectl -n vmweave-system get deploy,pods,svc
kubectl -n vmweave-system logs deploy/vmweave-controller
kubectl get crd gpuprofiles.vmweave.io gpurequests.vmweave.io \
  sharedmemorychannels.vmweave.io channelattachments.vmweave.io
```

도구는 schema를 검증하고 새 CRD를 적용한 뒤 중앙 배포를 준비하고 Webhook을 등록합니다.
구 `flyt.dev` CRD는 삭제하지 않습니다. Helm의 CRD upgrade를 가정하지 않습니다.

Controller는 기본 1 replica이며 Lease election을 사용합니다. Webhook은 별도 SA/Deployment입니다.
다중 replica의 전체 장애 행렬은 별도 검증 대상입니다. 일반 VM도 관리 namespace에 둘 수 있지만,
Webhook 서비스 장애는 해당 namespace의 관련 admission 요청을 차단할 수 있습니다.

## 다음 단계

[사용자 namespace](namespaces.md) → [첫 VM 실행](first-vm.md).
