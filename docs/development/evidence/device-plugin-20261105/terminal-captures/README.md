# Device Plugin 실제 SSH 터미널 캡처

상세 설명과 8개 PNG는 [검증 문서](../../../device-plugin-validation-2026-11-05.md)의
“실제 터미널 PNG 캡처” 절을 참조한다.

- `01`~`08`: 원본 PNG 및 화면의 `tmux capture-pane` TXT. 화면 자동 줄바꿈도 원문대로 보존한다.
- `gpu-pod.yaml`, `device-plugin-values.yaml`: 실제 제출한 입력.
- `pod-api.json`, `plugin-daemonset.json`, `node-api.json`, `guest-status.json`: 실행 후 조회 원본.
- `capture.json`, `commands.json`: UTC 시각, 해상도, 도구 버전, 실행 명령·종료 코드.
- `cleanup.json`: 촬영 후 정상 VM 종료·채널 회수 확인.
- `SHA256SUMS`: 이 디렉터리 파일의 바이트 검증 (`sha256sum -c SHA256SUMS`).

`capture.cjs`는 Playwright·tmux·ttyd를 사용한다. SSH 설정은 저장소 밖의 JSON에서 받는다.
인자는 `ssh`(대화형 argv), `sshExec`(명령 실행 argv), `output`, `scratch`, `ttyd`다.
VM의 대화형 bash는 실제 hostname prompt를 유지하고 `PROMPT_COMMAND`에서 직전 종료 코드를
`/tmp/vmweave-capture-status`에 기록한다. 준비된 파일과 새 시험 namespace가 필요하다.
전체 촬영은 Plugin이 제거된 전용 시험 VM을 전제로 하며, 임의 운영 VM에서 재실행하는 자동 설치기는 아니다.
`frames`로 특정 화면만 선택하고 `append: true`로 후속 촬영 메타데이터를 추가할 수 있다.
이번에는 설치 직후 allocatable 0 관측을 보존하고 최종 1 상태를 08번으로 추가했다.

SSH 키·kubeconfig·레지스트리 인증 정보는 이 디렉터리에 포함하지 않는다.
