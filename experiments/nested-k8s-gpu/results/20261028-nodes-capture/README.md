# Control Plane VM의 실제 노드 목록 캡처

캡처 시각: 2026-10-28T20:22:47.337000+09:00 (KST). 화면의 Guest `date` 출력은 UTC다.

`vw-k8s-cp-01`에 SSH로 접속한 실제 터미널에서 `kubectl get nodes -o wide`를 실행했다.
같은 화면에 Guest hostname과 `kubernetes-admin@vmweave-nested` context를 표시했다.

- `vw-k8s-cp-01`: Ready, control-plane, `10.245.0.10`
- `vw-k8s-worker-01`: Ready, `10.245.0.11`

Worker의 ROLES `<none>`은 역할 라벨 표시이며, 두 노드는 같은 API의 노드 목록에 등록되어 있다.
이번 수집은 현재 상태 조회이며 이전 GPU 시험이나 장애 주입을 재실행하지 않았다.

![실제 Control Plane 터미널](control-plane-kubectl-get-nodes-wide.png)

[PNG 원본](control-plane-kubectl-get-nodes-wide.png) · [명령 출력 원문](terminal.txt) ·
[캡처 메타데이터](capture.json) · [접속 대상 식별 정보](connection.json)

이미지는 실제 ttyd/tmux SSH 세션을 Playwright로 캡처한 원본이며 편집하지 않았다.
기존 `20261028-minimal` 실험 증거 및 해시는 변경하지 않았다.
