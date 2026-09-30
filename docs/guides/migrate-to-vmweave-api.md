# 기존 flyt API에서 이전

새 API는 구 API의 이름 변경이 아니라 별도 CRD입니다. 새 객체의 UID를 다시 연결해야 합니다.
이전 백업 브랜치와 비공개 데이터 snapshot을 확보하고 구controller가 정상 회수를 마친 뒤 수행합니다.

```sh
python3 scripts/operator/migrate.py --namespace OLD_NAMESPACE --output .local/migration-plan
```

기본 동작은 조회와 plan 저장입니다. `--apply`는 구controller 중단·VMI 없음·모든 구Channel Released를
검사하고 Profile/Request를 새 API에 생성합니다. 동일 이름의 외부 객체를 덮어쓰지 않습니다.
완료 Channel/Attachment 이력은 구 API와 백업에 남깁니다.

새 실행까지 준비할 때는 `--channel NAME`과 `--helper-image`, `--worker-image`, `--hook-image`의
새 digest를 명시합니다. VM/PVC UID를 확인하고 Halted VM의 구binding을 정리한 뒤 새Channel을 만듭니다.
새 Channel이 만들어지면 중앙 active Operator가 새 할당을 시작할 수 있으므로 scope 전환을 조율합니다.
VM 시작은 별도입니다. 신·구 controller가 같은 VM/PVC를 동시에 관리하지 않게 합니다.

`before-*.json`, VM 원본, checkpoint/result를 보존합니다. 구 status/allocation/Attachment/finalizer를
복사하지 않습니다. 새 실행 전에 rollback하면 신규 범위를 닫고 구설정을 복구할 수 있습니다.
새 할당 이후에는 먼저 신측 정상 회수를 마친 후 구API의 새요청을 만들어야 합니다.

Draining/증거 누락 대상은 자동 이전하지 않습니다. API나 finalizer를 먼저 삭제하지 않습니다.
구CRD의 삭제는 모든 구CR을 삭제하므로 백업·의존성 확인 후 별도로 결정합니다.

새 allocation의 helper/Worker/ServiceAccount/Role 이름은 Channel UID가 포함된 prefix를 사용합니다.
따라서 구 API의 완료된 동명 Pod/RBAC 이력을 삭제하거나 소유권을 넘겨받지 않습니다.
기존 신API allocation은 status에 기록된 이름 규칙을 유지합니다.
