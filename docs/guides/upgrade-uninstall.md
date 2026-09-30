# 업그레이드와 제거

같은 관리 범위/모드에서 이미지를 갱신할 때는 [공통 설치 도구](../getting-started/install.md)를 사용합니다.
기존 Webhook 등록은 유지합니다. Recreate 전략은 일시적인 admission 중단을 수반하므로 유지보수 시간에 수행합니다.
인증서 교체는 CA 신뢰 기간 중첩과 새 인증서 연결을 먼저 검증합니다.

## 관리 목록 또는 모드 변경

설치 도구는 scope/mode 변경을 거부합니다. chart 0.2.1부터 `maintenance.enabled=true`로
Controller만 중지하고 Webhook을 유지할 수 있습니다. `controller.replicas`는 정상 재개할 값(기본 1)으로 둡니다.
이 설정은 drain을 자동 수행하지 않습니다. 아래 명령은 기존 release 이름이 `vmweave`, system namespace가
`vmweave-system`일 때이며, release 이름이 다르면 모든 명령을 함께 변경합니다.

1. 신규 실험 요청을 중단합니다. 현재 관리 범위의 active Channel을 drain하고 Released·detach를 확인합니다.
   해제할 namespace에서는 완료 Channel도 **기존 Controller가 살아 있을 때** 삭제하고 삭제 완료를 기다립니다.
   남은 Worker/VMI와 finalizer가 없음을 확인합니다. 증거 없는 Draining은 여기서 진행하지 않습니다.
2. 값과 객체 정의를 비공개 경로에 백업합니다. 현재 CRD와 호환되는 chart를 사용하며
   이 절차에서 API schema·TLS·이미지를 동시에 교체하지 않습니다.

```sh
mkdir -p .local/scope-maintenance
chmod 700 .local/scope-maintenance
helm get values vmweave -n vmweave-system -o json > .local/scope-maintenance/before.json
cp .local/scope-maintenance/before.json .local/scope-maintenance/after.json
# after.json의 management.namespaces 또는 mode를 수정합니다.
# 새 namespace는 먼저 생성합니다. active에는 activeModeAcknowledged=true가 필요합니다.
helm template vmweave charts/vmweave-operator -n vmweave-system \
  -f .local/scope-maintenance/after.json > .local/scope-maintenance/rendered.yaml
```

3. 먼저 **기존 범위 그대로** Controller를 중지하고 실제 Pod 종료를 확인합니다.

```sh
helm upgrade vmweave charts/vmweave-operator -n vmweave-system \
  -f .local/scope-maintenance/before.json --set maintenance.enabled=true --wait --timeout=180s
kubectl -n vmweave-system wait --for=delete pod -l app=vmweave-controller --timeout=60s
```

4. 유지보수를 유지한 채 새 범위/모드를 적용합니다. 같은 values로 RBAC·Webhook selector와 실행 인자가 바뀝니다.

```sh
helm upgrade vmweave charts/vmweave-operator -n vmweave-system \
  -f .local/scope-maintenance/after.json --set maintenance.enabled=true --wait --timeout=180s
kubectl -n vmweave-system rollout status deployment/vmweave-webhook --timeout=120s
kubectl get validatingwebhookconfiguration vmweave-system-vmweave -o yaml
kubectl -n vmweave-system get deployment vmweave-controller
```

Controller의 desired replicas=0과 Webhook의 새 namespace selector를 확인합니다.
각 유지할 namespace에서 [권한 검사](../getting-started/namespaces.md)를 수행하고,
존재하는 대표 VM에 다음과 같은 서버 dry-run 요청으로 admission 연결을 검사합니다.
실제 namespace/VM 이름으로 바꿉니다. VM이 없는 신규 namespace는 준비한 유효 VM manifest에
`kubectl apply --dry-run=server -f FILE`을 사용합니다. 예상한 정책 거부와 연결/TLS 오류를 구분합니다.

```sh
kubectl -n YOUR_NAMESPACE annotate vm YOUR_VM vmweave.io/maintenance-check=passed \
  --overwrite --dry-run=server
```

5. 검사가 통과하면 Controller를 재개하고 값과 readiness를 보관합니다.

```sh
helm upgrade vmweave charts/vmweave-operator -n vmweave-system \
  -f .local/scope-maintenance/after.json --set maintenance.enabled=false --wait --timeout=180s
kubectl -n vmweave-system rollout status deployment/vmweave-controller --timeout=120s
helm get values vmweave -n vmweave-system -o json > .local/scope-maintenance/result.json
```

어느 단계든 실패하면 Controller를 중지한 상태에서 원인을 해결합니다.
새 할당을 시작하기 전에는 before.json을 maintenance=true로 적용하고 기존 Webhook·권한 검사를 거쳐
maintenance=false로 복귀할 수 있습니다. 새 할당이 시작된 뒤에는 먼저 새 범위에서 회수해야 합니다.
`--skip-schema-validation`이나 finalizer 강제 제거를 표준 절차로 사용하지 않습니다.

## namespace와 데이터 정리

1. 실행 결과·객체 정의·디스크를 백업하고 복구 가능성을 확인합니다. containerDisk 변경분은 VMI 종료 전에 보관합니다.
2. 할당을 회수하고 Channel을 정상 삭제합니다. Controller·권한을 먼저 제거하지 않습니다.
3. 위 절차로 namespace를 관리 목록에서 제외합니다. 빈 관리 목록은 허용하지 않으므로
   모든 관리 범위를 없앨 때는 전체 중앙 release 제거 절차를 사용합니다.
4. VM과 namespace를 삭제하고 Terminating 잔류 여부를 확인합니다.
5. Retain PV는 별도 데이터 수명 주기입니다. 백업·비사용·전용 경로를 확인한 후 PV와 노드 파일을 정리합니다.

복구는 namespace·PV/PVC 연결과 디스크 데이터를 복원한 뒤 정지 VM을 만들고 새 UID로 Request/Channel을 생성합니다.
과거 allocation/status/finalizer를 새 실행에 복사하지 않습니다. 디스크 복구와 GPU 세션 복원은 다른 작업입니다.

## 중앙 release 제거

모든 관리 namespace의 할당 회수와 Channel 삭제를 완료한 뒤 수행합니다.

```sh
helm uninstall vmweave -n vmweave-system --wait --timeout=180s
```

CRD, 사용자 VM/PVC, system namespace 및 수동 생성 TLS Secret은 별도입니다.
구 `flyt.dev`와 신 `vmweave.io` CRD 삭제는 모든 해당 CR을 삭제하므로 전체 namespace의 의존성·백업을 먼저 확인합니다.
namespace가 이미 Terminating이면 신규 reclaim Pod를 만들 수 없으므로 사전에 회수를 완료해야 합니다.
