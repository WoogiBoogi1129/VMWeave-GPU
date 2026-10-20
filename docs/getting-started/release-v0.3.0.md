# 배포 릴리스 v0.3.0

2026-10-20(KST), `0ff184a649c59eeb3145e5ec5340447918d2ce02`에서 게시했습니다.
태그는 `v0.3.0`, Helm chart 버전은 `0.3.0`입니다. 과거 Flyt v1.0.0과는 별도의
현재 VMWeave 배포 버전입니다.

## 게시 산출물

모든 이미지는 `ghcr.io/woogiboogi1129/` 아래에 있으며 태그는 `v0.3.0`입니다.

| 이미지 | 역할 |
|---|---|
| vmweave-operator | 중앙 Controller·Webhook |
| vmweave-helper | backing 준비·회수 |
| vmweave-worker | SHM CUDA 실행 |
| vmweave-hook | KubeVirt v1.9.0용 hook |
| vmweave-guest-artifacts | Guest 라이브러리·broker·GPU smoke |
| vmweave-hami | 수정 HAMi 라이브러리를 포함한 device-plugin 이미지 |

[전체 이미지·차트 digest 및 CI 기록](../../deploy/releases/v0.3.0.json)을 고정 참조로 사용합니다.
[Operator digest가 입력된 values 예제](../../deploy/releases/v0.3.0-values.json)는
`team-a` namespace, active 모드, 기존 TLS Secret 방식을 사용합니다.
namespace·TLS·노드 설정을 실제 환경에 맞추고 [설치 절차](portable-deployment.md)를 따릅니다.

## 다운로드

차트는 registry 로그인 없이 다운로드할 수 있습니다.

```sh
helm pull oci://ghcr.io/woogiboogi1129/charts/vmweave-operator --version 0.3.0
```

OCI chart digest:
`sha256:7a34df1f3640136b2b9c3ccfc08fd166dbb844465ea6ee95ab0eb8b460034e42`.
다운로드 출력의 digest를 확인합니다. Helm의 `.tgz` 파일 SHA256과 OCI manifest digest는
서로 다른 값이므로 동일한 값으로 비교하지 않습니다.

## 검증 범위

- 이미지·HAMi·차트 게시 CI 모두 성공.
- 비어 있는 registry 인증 설정으로 6종 이미지 metadata 조회 및 revision label 비교 성공.
- Helm 차트 익명 다운로드 및 릴리스 소스 내용 비교 성공.
- Guest artifacts 익명 다운로드·내부 체크섬·source revision 확인 성공.
- 실제 GPU 클러스터 설치·실행은 별도 검증 대상입니다. 게시 성공은 GPU 실행 성공을 뜻하지 않습니다.

[이미지 CI](https://github.com/WoogiBoogi1129/VMWeave-GPU/actions/runs/39398769193),
[HAMi CI](https://github.com/WoogiBoogi1129/VMWeave-GPU/actions/runs/39398769150),
[차트 CI](https://github.com/WoogiBoogi1129/VMWeave-GPU/actions/runs/39398769179).
