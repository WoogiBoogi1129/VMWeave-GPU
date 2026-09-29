# 저장소 구조와 이동 기록

정리 기준은 `62951a7`이며 Git 추적 파일 3,503개(약 319 MB)를 역할별로 분류했습니다.
로컬 빌드 산출물·가상환경·비공개 설정은 이 수에 포함하지 않습니다.

| 경로 | 역할과 보존 정책 |
|---|---|
| 루트 Markdown·LICENSE·NOTICE | 현재 소개·기여·출처·보안 정책 |
| `runtime/shm/` | 현재 실행 소스와 ABI 계약 |
| `charts/`, `deploy/` | Helm chart, CRD, 배포 예제; CRD 복사본 일치 검사 |
| `images/` | 컨테이너 빌드 입력; 호환 이미지 이름 유지 |
| `scripts/` | 빌드·운영·설치·문서 검증 도구 |
| `tests/` | CPU 및 CUDA 개발 검증 |
| `experiments/evidence/` | 실험 실행·수집·분석 도구 |
| `experiments/evidence/results/` | 기존 3,014개 증거 파일, 내용과 경로 보존 |
| 기타 `experiments/` | SHM 전환의 단계별 설계 기록 |
| `docs/` | 현재 안내·평가 요약과 문서 사이트 |
| `legacy/rpc/` | 이전 구현, 기본 빌드에서 제외 |
| `legacy/docs/` | 이전 문서; 당시 상태와 명령 보존 |
| `artifacts/`, `results/` | 기존 README 보존; 로컬 산출물 Git 제외 |
| `.github/` | 검증·이미지·Pages workflow |
| `versions.lock.yaml`, `Makefile`, `.gitignore`, `.gitattributes` | 버전·명령·추적·증거 줄바꿈 정책 |

## 이동 내역

| 이전 경로 | 현재 경로 |
|---|---|
| `experiments/shm-contract/` | `runtime/shm/shm-contract/` |
| `experiments/shm-queue/` | `runtime/shm/shm-queue/` |
| `experiments/cuda-dispatch/` | `runtime/shm/cuda-dispatch/` |
| `docs/installation/`의 C/CUDA·셸·values 파일 | `scripts/installation/` |
| 기존 설명·과거 보고서 | `legacy/docs/` |

[파일별 이동 목록](moves.json)에는 이동한 48개 파일을 기록했습니다.
이전 Markdown 주소에는 현재 안내와 과거 원문을 연결하는 호환 페이지를 남겼습니다.
역사 문서의 상대 링크는 정리 전 커밋에 고정합니다. 기존 증거의 경로와 해시는 변경하지 않습니다.

## 변경 범위

표시 이름과 저장소 주소는 VMWeave-GPU로 정리했습니다.
CRD group/version, 환경변수, 라이브러리, chart·이미지 이름의 변경은 별도의 호환성 작업입니다.
이 정리에서 런타임 알고리즘이나 GPU 실험의 수치를 바꾸지 않습니다.

문서 사이트에는 선택한 SVG 그림만 복사하고 원본과 SHA256을 연결합니다.
전체 결과나 로컬 산출물을 사이트에 복제하지 않습니다. Git 이력을 다시 쓰지 않습니다. `.dockerignore`로 로컬 산출물·증거 묶음을 이미지 빌드 context에서 제외하고, 중복 COPY를 제거했습니다.
