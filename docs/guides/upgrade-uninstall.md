# 업그레이드와 제거

같은 관리 범위/모드에서 Operator image를 갱신할 때는 공통 설치 도구를 사용합니다.
기존 Webhook은 등록된 상태로 유지합니다. 기본 Recreate 전략은 일시적인 admission 중단을 수반합니다.
인증서 파일은 TLS Secret으로 공급하며 인증서/CA 변경 시 overlap과 정상 연결을 먼저 검증합니다.

## 관리 목록 또는 모드 변경

현재 자동 rolling scope 전환은 제공하지 않습니다. 설치 도구는 해당 변경을 거부합니다.
유지보수 창에서 다음 순서를 따릅니다.

1. 대상의 신규 요청을 중단하고 모든 active Channel을 정상 drain/reclaim합니다.
2. 남은 finalizer와 Worker/VMI가 없는지 확인합니다. Released Channel 삭제도 증거가 필요합니다.
3. 중앙 controller를 0으로 scale하고 종료를 확인합니다. 기존 webhook은 유지합니다.
4. 새 관리 목록에 필요한 RoleBinding과 준비된 webhook을 적용합니다. 두 배포의 범위/인증이 일치해야 합니다.
5. webhook 정상 검증 후 controller를 재개합니다. 범위를 뺄 때는 회수 후 권한을 제거합니다.

raw Helm upgrade는 이 순서를 자동으로 보장하지 않습니다. Helm 설치 이력과 값·UID를 기록합니다.

## 제거

중앙 release 제거 전 관리 namespace에 남은 할당과 finalizer를 점검합니다.
controller/webhook을 먼저 제거하면 회수와 admission이 진행되지 않을 수 있습니다.

CRD와 사용자 CR/PVC 및 namespace는 별도 데이터 수명 주기를 갖습니다. `Retain` PV의 데이터를
namespace 삭제가 자동으로 제거하지 않습니다. 구 `flyt.dev` CRD도 일반 uninstall에서 삭제하지 않습니다.
이미 Terminating인 namespace에는 신규 reclaim Pod를 만들 수 없으므로 사전 회수를 수행해야 합니다.
