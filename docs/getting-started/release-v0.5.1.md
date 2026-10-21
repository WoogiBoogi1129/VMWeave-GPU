# 배포 릴리스 v0.5.1

2026-10-22(KST), `b9767652292179bef82f47be20b633a205d19824`에서
이미지 7종과 Operator Helm chart `0.5.1`을 게시했습니다.
`v0.5.0`은 덮어쓰지 않고 보존하며, CUDA 확장 함수 이름까지 보완한 `v0.5.1`을 사용합니다.

## 변경 사항

기본 이름은 `VMWEAVE_*`, `vmweave_*`, `/opt/vmweave`입니다.
기존 환경변수·공개 심볼·헤더·설치 경로는 호환 alias로 유지합니다.
`vmweaveRegisterKernelABI`와 기존 확장 함수도 같은 구현을 가리킵니다.
wire magic, 숫자 API ID, 기존 API 리소스와 공유 mount 경계는 유지합니다.
자세한 규칙은 [명칭 전환 문서](../development/naming-migration.md)에 있습니다.

Guest 공통 경로의 device/context 상태 캐시는 `VMWEAVE_STATE_CACHE=1`로
활성화합니다. 기본값은 비활성이며, 장애 관측·무효화와 lease의 한계는
[상태 캐시 문서](../runtime/state-cache.md)에 설명합니다.

## 산출물과 설치

[이미지 7종·차트 digest 및 CI 기록](../../deploy/releases/v0.5.1.json),
[digest 고정 values 예제](../../deploy/releases/v0.5.1-values.json)를 제공합니다.
이미지는 `ghcr.io/woogiboogi1129/vmweave-<component>:v0.5.1`이며,
component는 operator, helper, worker, hook, guest-artifacts, hami, hami-dra입니다.

```sh
helm pull oci://ghcr.io/woogiboogi1129/charts/vmweave-operator --version 0.5.1
```

OCI chart digest는 `sha256:827b3c430aef8820a43d1bd55792fbcad707ad8d2a3676bb22e14733232649b4`입니다.
[설치 절차](portable-deployment.md)를 따르며, 구형 컨트롤러가 있는 환경의
설치·이전 유틸리티는 `6e06916` 이후 main 버전을 사용합니다.
이 후속 변경은 구형 `FLYT_MODE` 감지와 보조 CPU 이미지 빌더를 보완하며,
게시한 runtime·Operator·이미지 레시피·차트 내용은 변경하지 않습니다.
DRA Driver chart는 기존 upstream `0.1.1`을 유지하고 이미지 digest를 갱신합니다.

## 검증

제어 테스트 81개, 배포 테스트 16개, Go vet/race test, 문서·저장소 검사와
GPU 없는 runtime 이미지 회귀를 통과했습니다. 이미지 게시 CI와 다운로드한
Guest 파일의 체크섬, 차트 파일 11개의 소스 일치도 확인했습니다.

[실제 GPU 이름 변경 비교](../../experiments/ai-passthrough/results/20261022-naming/README.md)는
단일 workload로 수행했습니다. 변경 후 18,598 samples/s는 변경 전 18,509 및
복원 18,822 사이였으며, 1·10·100 step의 loss·가중치·gradient는 완전히 같았습니다.
이는 단일 비교이며 통계적 동등성이나 passthrough 성능 회복의 증명은 아닙니다.
공개 이미지로 현재 VM의 GPU 실행, 캐시 활성 상태의 Worker 장애 오류 999,
기존 이름을 사용하는 새 세션 복구를 확인했습니다. Operator chart 0.5.1 및
DRA Driver 이미지 적용 결과와 롤백 위치는
[적용 기록](../../experiments/ai-passthrough/results/20261022-naming/README.md)에 있습니다.
