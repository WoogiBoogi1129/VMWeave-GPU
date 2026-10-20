# 배포 릴리스 v0.4.0

2026-10-21(KST), `804ed96860bf68138ffbd3bcde5df20bd74bc6c4`에서 게시했습니다.
태그는 `v0.4.0`, VMWeave Operator Helm chart 버전은 `0.4.0`입니다.
기존 HAMi backend를 유지하면서 선택적인 HAMi DRA backend를 추가했습니다.

## 게시 산출물

이미지 경로는 `ghcr.io/woogiboogi1129/vmweave-<이름>:v0.4.0`입니다.

| 이름 | 역할 |
|---|---|
| operator | Controller·Webhook, HAMi 및 DRA 할당 |
| helper | backing 준비·회수 |
| worker | SHM CUDA 실행 |
| hook | KubeVirt v1.9.0용 hook |
| guest-artifacts | Guest 라이브러리·broker·GPU smoke |
| hami | 수정 HAMi 라이브러리를 포함한 device-plugin |
| hami-dra | GPU UUID 선택 및 수정 HAMi-core를 포함한 DRA Driver |

[이미지·차트 digest와 CI 기록](../../deploy/releases/v0.4.0.json),
[Operator digest를 고정한 values 예제](../../deploy/releases/v0.4.0-values.json)를 제공합니다.
예제의 namespace 및 TLS 설정은 실제 환경에 맞춰야 합니다.

## 설치와 업데이트

```sh
helm pull oci://ghcr.io/woogiboogi1129/charts/vmweave-operator --version 0.4.0
```

OCI chart digest는
`sha256:42b4873d1fb63aaf288c0839d10d6291ba7f7776b32301a290bdd4b74b1bf8df`입니다.

[설치 절차](portable-deployment.md)를 따릅니다. 기존 설치를 업데이트할 때는
릴리스의 CRD를 먼저 적용해야 합니다. Helm upgrade는 CRD를 자동으로 갱신하지 않습니다.
기존 GPUProfile은 HAMi backend를 유지합니다. DRA를 사용하려면
[HAMi DRA 설치 절차](hami-dra.md)에 따라 별도의 Driver와 DeviceClass를 준비하고
`backend: hami-dra`인 새 GPUProfile을 만듭니다.

게시된 OCI 차트는 VMWeave Operator용입니다. DRA Driver의 Helm 차트는
문서에 고정된 upstream commit의 chart 0.1.1을 사용합니다.

## 검증 범위

게시 검증과 GPU 실행 검증은 구분합니다. 이미지별 digest·revision label과
익명 조회, 차트 익명 다운로드·소스 내용 비교 결과는 릴리스 lock에 기록합니다.
Guest 이미지는 익명 다운로드 후 내부 파일 체크섬을 확인했습니다. DRA 이미지도
익명 다운로드 후 바이너리 기동·수정 라이브러리 설치·기존 메모리 매핑 유지 검증을
통과했습니다. revision label은 암호학적인 출처 증명이 아닙니다.

DRA 기능은 릴리스 이전 로컬 빌드로 Kubernetes 1.37.0 / CRI-O 1.37.0의
단일 GPU 노드에서 검증했습니다. VM GPU 복사·커널 실행, 메모리 제한,
연산 제한, 재할당·장애 정리 결과는
[GPU 검증 기록](../../experiments/dra-smoke/README.md)에 있습니다.
이번 공개 이미지로 GPU 실행을 다시 검증하거나 다른 클러스터·다중 노드에서
검증한 것은 아닙니다.
