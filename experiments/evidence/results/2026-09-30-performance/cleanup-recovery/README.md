# 측정 후 자원 삭제 실패와 복구

전체 성능 측정과 원본 검증을 마친 뒤 `cleanup.py`의 첫 채널 삭제가 시간 초과됐습니다.
`perf-c-r1-100`은 이미 `Released / DetachAndReclamationConfirmed`였지만,
Foreground 삭제가 소유된 ChannelAttachment를 먼저 지웠습니다. 현재 제어기는
삭제 중인 Released 채널에도 Drain을 다시 실행하므로 분리 증거를 찾지 못해
`Draining / AwaitingDetachEvidence`에 머물렀습니다.

다음 채널 `perf-c-r1-25`에 UID 조건을 둔 Background 삭제를 적용하자
제어기가 정상적으로 finalizer를 처리하고 삭제됐습니다. 이후 채널 삭제만
Background로 수정했습니다. VM·PVC 등 다른 자원의 삭제 정책은 유지했습니다.
제어기 바이너리와 측정 경로는 이 복구에서 변경하지 않았습니다.

첫 채널은 이미 증거 자원이 삭제돼 정상 경로로 다시 처리할 수 없었습니다.
다음 조건을 모두 확인한 뒤 **그 채널 한 개의 finalizer를 수동 해제**했습니다.

- 이전에 공개한 커밋 `67cffa2`의 Released 원본과 현재 원본이 바이트 단위로 동일.
- 채널 UID, allocation·generation·GPU·Worker·VMI 식별자와 spec이 기존 기록과 일치.
- 동일 UID의 VM이 Halted이고 VMI·Worker·PVC를 마운트한 Pod가 없음.
- 대상 GPU에 연산 프로세스가 없고, 동일 PVC/PV의 로컬 backing 디렉터리가 비어 있음.
- 노드가 Ready. UID·resourceVersion·finalizer 목록을 JSON Patch test로 다시 대조.

이는 정상 자동 회수로 표현하지 않는 관리 작업입니다. 새로운 Detached 기록이나
벤치마크 성공 기록을 만들지 않았으며 측정 결과도 변경하지 않았습니다.
증거는 `manual-finalization-preconditions.json`, `manual-finalization-result.json`,
`background-before.json`, `background-result.json`과 상위 `commands.jsonl`에 있습니다.
최초 오류는 상위 `postprocess-failure.json`과 실제 정리 로그에 그대로 보존합니다.

최종 정리는 `--resume-cleanup`으로 재개하며 이미 보존된 모니터링을 재설치하지 않습니다.
최종 상태는 상위 `postprocess-complete.json` 및 `final-audit.json`으로 확인합니다.
이 사건은 성능 측정 후 정리 도구의 삭제 방식과 제어기 수명 주기의 결합 문제이며,
성능 측정 도중의 실행 중단과는 별개입니다. 제어기가 Foreground 삭제에서도
종료 상태를 안전하게 유지하도록 하는 일반적인 수정·회귀 검증은 남은 개발 과제입니다.
