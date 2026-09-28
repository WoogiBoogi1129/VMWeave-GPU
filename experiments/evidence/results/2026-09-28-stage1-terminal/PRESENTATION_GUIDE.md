# 발표용 구성 — 1단계

핵심 주장: **VM에 요청한 GPU 설정이 Worker에 전달되고, 해당 Worker를 통해 GPU 프로그램이 실행됨을 확인했다.**
UID·inode 전체 목록과 라이브러리 해시는 질의응답용 부록에 둔다. 본문은 실제 명령과 핵심 출력의 대응에 집중한다.

## 첫 장: 요청한 GPU 설정이 실제 Worker에 적용되는가?

주 화면: [03-settings.png](slide-excerpts/03-settings.png). 빈 하단만 제외한 실제 터미널 발췌다.

화면 위의 kubectl 명령은 GPU 요청을, 아래 명령은 Worker limits를 조회한다.
발표자가 가리킬 값은 `memory: 4096Mi ↔ gpumem: 4096`, `compute: 50 ↔ gpucores: 50`, GPU 개수 1이다.

설명 문장:

> “메모리 4 GiB와 연산 설정값 50을 요청했습니다. 실제 Worker를 조회했을 때도 같은 값이 적용됐습니다.”

요청 전후 절차를 보여줄 때는 [01-request](terminal-captures/01-request.png) →
[02-vm-worker](terminal-captures/02-vm-worker.png) → [03-settings](terminal-captures/03-settings.png)
순서로 화면을 교체한다. 세 터미널 전체를 한 슬라이드에 작게 넣지 않는다.
현재 검증은 설정 전달이며 50% 이용률 보장이나 한도 초과 거절을 뜻하지 않는다.

## 둘째 장: VM의 프로그램이 실제 GPU에서 실행되는가?

먼저 [04-guest-command](terminal-captures/04-guest-command.png)에서 Guest 실행을 짧게 보여준다.
이어서 [05-gpu-pid](slide-excerpts/05-gpu-pid.png)를 크게 표시한다.

설명 문장:

> “VM에서 CUDA 프로그램을 실행했습니다. 이 VM에 연결된 Worker의 호스트 PID는 413150이고,
> nvidia-smi에도 같은 PID가 GPU 프로세스로 나타납니다.”

마지막으로 같은 슬라이드의 화면을 [06-result](slide-excerpts/06-result.png)로 교체한다.

> “프로그램이 정상 종료됐고, 최종 출력 524,288개를 검사한 결과 불일치는 0개였습니다.”

아래에는 기존 3회 검증과 이번 시연을 구분해 “기존 독립 검증 3회, 별도 절차 시연 1회 완료”라고 적을 수 있다.
이번 첫 시연의 SSH 정지와 회수 기록은 보고서에 공개돼 있다. 전체 시도 성공률 100%로 표현하지 않는다.

## 영상 사용

[145초 원본 터미널](stage1.cast)과 [1배속 재생 영상](terminal-captures/stage1-terminal-replay.webm)을 제공한다.
발표에서는 [chapters.json](chapters.json)의 설정 확인·GPU PID·결과 시점으로 이동해 설명할 수 있다.
일시정지·장면 전환을 하더라도 명령과 출력의 연결을 남긴다. 영상이 실제 터미널 녹화의 재생본임을 표시한다.

Grafana의 시계열은 뒤의 메모리 사용량·연산 이용률 분석에 사용한다. 이번 단계의 핵심은 요청값과
실행 객체의 대응이므로 kubectl, nvidia-smi, Guest stdout이 직접적인 근거다.
