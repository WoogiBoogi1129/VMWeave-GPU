# 배포 릴리스 v0.5.2

2026-10-22(KST) 릴리스의 소스는
`4f2ad748aa9fb9892e3e72ab18e559d6d8f81800`입니다.
Guest 공통 호출 경로에 동일한 BLAS math mode 설정의 반복 전달을 생략하는
선택적 최적화를 추가했습니다. 기존 릴리스와 호환 alias는 보존합니다.

## 기능과 활성화

기능은 **기본 비활성**입니다. 새 애플리케이션 프로세스에서 두 옵션을 설정합니다.

```sh
VMWEAVE_STATE_CACHE=1 VMWEAVE_BLAS_MATH_CACHE=1 your-application
```

같은 세션·handle에서 마지막 성공한 설정만 재사용합니다. 최초 설정·값 변경·용량
초과는 전달하고, 객체 생성/삭제·오류·device 변경·세션 종료는 기록을 무효화합니다.
실제 계산과 stream/workspace 설정은 생략하지 않습니다.
기존 health lease는 원격 생존의 즉시 보증이 아닙니다. 매 설정마다 원격 검증이
필요한 애플리케이션은 기능을 끄십시오. 상세 계약과 통계는
[상태 캐시 문서](../runtime/state-cache.md)에 있습니다.

## 공개 산출물

[이미지 7종·차트 digest와 CI 기록](../../deploy/releases/v0.5.2.json),
[digest 고정 values](../../deploy/releases/v0.5.2-values.json)를 제공합니다.
이미지 태그는 `ghcr.io/woogiboogi1129/vmweave-<component>:v0.5.2`이며,
component는 operator, helper, worker, hook, guest-artifacts, hami, hami-dra입니다.

```sh
helm pull oci://ghcr.io/woogiboogi1129/charts/vmweave-operator --version 0.5.2
```

DRA Driver는 upstream chart `0.1.1`과 기존 장치 선택 설정을 유지하고 이미지
버전만 갱신합니다. Classic upstream HAMi 2.10.0은 기존 설치 그대로 사용합니다.
게시한 vmweave-hami 이미지를 해당 외부 의존성에 임의로 대체하지 않습니다.

## 검증과 성능 해석

[배포 전 구현·검증 보고서](../../experiments/ai-passthrough/results/20261022-math-cache/report.md)에
단일 small MLP/batch1024/resident/FP32 결과와 원시 데이터를 제공합니다.
3회 대조 모두 향상했지만 +7.0~38.2%로 변동이 컸습니다. 중앙값은 +10.3%이며,
첫 회의 큰 개선 원인은 분리하지 못했습니다. 고정된 개선율 또는 Passthrough
수준의 성능을 보장하지 않습니다. 학습 결과는 기준과 완전히 일치했습니다.

새 기능 테스트 16개, 기존 상태 캐시 회귀 20개, 실제 GPU 오류·Worker/broker 장애
및 새 세션/transport 복구 검증을 통과했습니다. 공개 바이너리를 다시 내려받아
회귀 테스트를 수행하며, 실제 배포 후 GPU copy/kernel 및 math 설정·조회 검증을
확인합니다. 게시·적용 완료 상태와 정확한 범위는
[운영 적용 기록](../../experiments/ai-passthrough/results/20261022-math-release/README.md)에 기록합니다.

## 비활성화와 롤백

옵션을 unset 또는 0으로 설정한 새 애플리케이션 프로세스는 기존 전달 경로를 사용합니다.
프로세스가 연결한 뒤 환경 변수만 수정해서는 설정이 바뀌지 않습니다.
전체 릴리스 롤백은 [v0.5.1](release-v0.5.1.md)의 Guest 패키지와 digest를 사용하며,
운영 적용 기록의 이전 Helm revision 및 채널 바인딩 복구 절차를 따릅니다.
