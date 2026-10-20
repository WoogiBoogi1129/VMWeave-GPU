# 다른 클러스터 배포 패키지 검증 — 2026-10-20

기준 main: `cab9dc59611287d6e6110f17b736126b694cdff2`.
배포 코드 커밋: `017ca59`.
작업 범위는 사용자 확인에 따라 **배포 코드·패키지 검증**까지다.
별도 GPU 클러스터는 준비되지 않았으며 기존 연구 클러스터를 변경하지 않았다.

## 변경

- 현재 `images/vmweave` 기반 Operator·Helper·Worker·Hook·Guest 이미지 CI.
- 기존 HAMi CI와 이미지 revision label을 맞추고 혼합 revision을 거부하는 digest lock 도구.
- Helm chart 0.3.0, 기존 TLS Secret 및 선택적 cert-manager Certificate/CA 주입.
- 동적으로 생성하는 Helper·Worker Pod의 namespace별 imagePullSecrets 전달.
- Guest 라이브러리·broker·설치 파일·GPU smoke·소스 revision·SHA256SUMS 패키지.
- 실행 중 broker 교체 거부 및 Guest 패키지 체크섬 검사.
- 읽기 전용 API preflight와 전용 VM의 GPU smoke/재시작 도구.
- 새 클러스터 설치, 인증서, HAMi, 로컬 PV, Guest, 업그레이드·삭제 문서.

## 검증과 범위

| 검사 | 결과 | 범위 |
|---|---|---|
| 배포 회귀 13개 | PASS | Helm 렌더링, 인증서 분기, Secret 전달, preflight 실패, smoke UID/회수 순서, 혼합 revision 거부 |
| 기존 Python control 57개 | PASS | 기존 제어·증거 계약 |
| Go vet / race tests / CRD 검사 | PASS | Operator 코드와 생성 Pod의 pull secret 전달 |
| Helm lint / package | PASS | 차트 문법·schema 및 tgz 생성 |
| 문서 계약·strict build·링크 | PASS | 설치 CLI 옵션과 사이트 링크 |
| Guest artifacts build / checksum | PASS | 실제 C 런타임 컴파일, Guest 패키지 파일 검증 |
| Operator build / 실행 파일 확인 | PASS | 고정 Go·distroless 기반 이미지, 비특권 이미지의 --help 실행 |
| Worker / Helper / Hook build | PASS | 현재 Containerfile과 고정 KubeVirt v1.9.0 shim |
| HAMi 설치 검사 | PASS | 기존 로컬 수정 이미지로 반복 설치·기존 inode 유지, 호스트/GPU 접근 없음 |

이미지 빌드는 로컬 Podman에서 실행했으며 일부 기반 이미지/패키지 계층 캐시를 사용했다.
CPU 회귀 테스트의 모의 API와 실제 GPU 검증은 구분한다. 문법·렌더링 성공은 admission
연속성이나 다른 GPU에서의 CUDA 실행 성공을 의미하지 않는다.
빌드·검사 로그는 `.local/portable-deployment-review/`에 보존한다.

## 미실행

- registry 이미지·Helm 차트 게시, GitHub Actions 실제 실행.
- 새 GPU 클러스터 신규 설치·실제 GPU smoke·VM 재시작·backing 파일 회수.
- 실제 cert-manager 발급·갱신·CA 회전 및 admission 연속성.
- 실제 클러스터의 업그레이드·롤백·삭제.
- 다른 GPU·Kubernetes/KubeVirt 조합, HA와 전체 장애 행렬.

릴리스 관리자는 모든 이미지/차트 CI 성공과 digest lock을 확인한 뒤 게시한 산출물을
설치 안내에 사용한다. 과거 v1.0.0 태그는 이 변경의 배포판이 아니다.
새 환경이 준비되면 [배포 절차](../getting-started/portable-deployment.md)의 완료 판정을 실행한다.
