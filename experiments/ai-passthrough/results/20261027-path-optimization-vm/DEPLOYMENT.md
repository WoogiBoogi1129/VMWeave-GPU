# 후속 배포 기록 — 2026-10-27

사용자가 기존 VMWeave 대비 개선을 근거로 명시적으로 교체 배포를 요청하여 v0.5.5를 발행하고
`gpu-4`의 `vmweave-test-a/vmweave-k8s-01`에 적용했다. main에는 개선 코드, 원시 실험 자료,
검증 자료와 릴리스 digest를 반영했다. Helm chart 0.5.5 / release revision 13이다.

원래 REPORT.md와 status.json의 배포 보류는 당시의 “Flyt보다 빠를 때만 배포” 조건에 따른
판정으로 보존한다. 이번 배포가 Flyt 대비 우위를 새로 입증한 것은 아니다. 측정 후보는
options-OFF 대조군 대비 실행시간 34.3% 감소, Flyt SHM 대비 10.0% 증가였다.
NEXT-STEPS.md의 추가 경로 개선 제안은 이번 배포에 구현한 내용이 아니다.

공개 아티팩트는 운영과 같은 50%/2 GiB 할당의 별도 VM에서 memset 커널 60건,
큰 복사 18건과 반복 비동기 전송, NW/LU/SRAD/SC 정확성 검사를 통과했다.
교체 후 운영 VM에서도 Guest 소스/바이너리 hash, 기본/캐시 GPU smoke, math-mode,
큰 복사 및 NW/LU 출력을 검증했다. VM·root/SHM PVC 식별자와 GPU 할당을 유지했다.
Compute Sanitizer의 기존 시작 실패는 여전히 미검증으로 남긴다.

[릴리스 상세](../../../../docs/releases/v0.5.5.md) ·
[digest 및 설정](../../../../deploy/releases/v0.5.5.json) ·
[검증 증거](../../../../deploy/releases/evidence/v0.5.5/)

기존 v0.5.4 Guest/환경 백업과 Helm revision 12, 기존 Profile/Request를 로컬에 보존했다.
새 로그인 세션에는 bulk/direct/native-memset 변수가 적용된다. sudo·서비스·Pod로 실행하는
앱은 런타임 안내에 따라 해당 변수를 명시적으로 전달해야 한다.

원래 실험의 evidence-sha256.json은 측정 당시 파일 집합을 검증하며, 이 후속 배포 기록은
별도 릴리스 증거로 관리한다.
