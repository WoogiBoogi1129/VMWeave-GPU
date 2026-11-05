# 저장소 구조 최적화 적용 결과

2026-11-05, [사전 검토](repository-structure-review-2026-11-05.md)의 우선순위에 따라 적용했다.
기준 커밋은 `223468c9afc270abe9bb935b08b3244f4481bcc1`이며 대규모 이동·삭제·이력 재작성은 하지 않았다.

| 대상 | 적용 내용 |
|---|---|
| 최신 정보 | [현재 릴리스 색인](../releases/index.md)과 `deploy/releases/current.json` 추가, chart lock 0.5.8 일치, README·nav·상태 문서 갱신 |
| 과거 설치 명령 | portable 문서의 v0.5.2 명령은 유지하면서 재현 대상 버전을 명시하고 현행 설치·업그레이드로 연결 |
| 배포 소스 | `tools/guest-smoke/`에 원본과 동일한 C 소스·출처 manifest 추가, Containerfile·현재 수동 준비·smoke 실행기 참조 변경 |
| 테스트 입력 | `tests/fixtures/evidence/`에 필요한 28개 원본 파일만 복사, 기존 Stage 1/2 판정 테스트가 사용하도록 변경 |
| CI | 이미지 COPY 입력의 변경 감지 누락 보완, Python 구문 검사의 하위 디렉터리 포함, 문서 workflow의 새 입력 포함 |
| 자료 관리 | 실험 23개 디렉터리의 색인, 최근 campaign 링크, 새 실험의 구조·대용량 자료·checksum 규칙 추가 |
| 링크 | 현행 runtime 링크 1개 수정, 역사 링크 18개는 원문 수정 없이 [별도 안내](../history/link-map.md) 제공 |
| 바이트 보존 | 새 fixture·smoke와 training-threeway checksum 대상에 개행 변환 방지 규칙 적용 |

배포용 smoke 1개와 fixture 28개는 출처 커밋의 Git blob과 바이트 단위로 동일함을 확인했다.
fixture 합계는 1,193,154 bytes이며 기존 3회 출력 배열 검증 범위를 축소하지 않았다.
배포 이미지에는 fixture가 필요하지 않아 Docker context에서 제외했다.
검증 함수 등 실험 소스의 의존은 유지하며 전체 실험 도구를 독립 패키지로 옮긴 것은 아니다.

새 검사는 chart와 버전 lock의 불일치, 공개 릴리스 pointer와 기록의 불일치,
fixture/smoke의 hash 변경, Containerfile COPY 입력과 이미지 CI path filter의 불일치를 탐지한다.
개발 중 chart 버전은 공개된 current release와 달라도 되도록 구분했다.

CPU 제어·chart workflow를 무조건 skip하는 최적화는 적용하지 않았다.
기존 필수 체크 이름·실행 동작을 유지하며, 실행 시간 축소는 branch protection과 의존 목록을 확인한 뒤 다룬다.
새 실험 규칙은 앞으로 생성하는 자료에 적용하고 기존 데이터의 외부 이전은 수행하지 않았다.

**검증**

- 기존 사용자 수정·미추적 문서를 섞지 않은 커밋 사본에 이번 변경만 적용해 문서 검사를 수행했다.
- CPU 제어 테스트: `experiments/evidence/results/`가 없는 임시 사본에서 129개 실행, 128개 통과·기존 skip 1개.
- 배포 테스트: 20개 통과. 버전 lock 오류·릴리스/chart 독립 버전·CRLF 바이트 변조 거부·이미지 변경 감지 회귀 검사 포함.
- 구조 검사·현행 CRD 복사본 검사·문서 CLI 계약 검사·MkDocs strict build·사이트 링크/anchor 검사 통과.
- 현행 문서의 상대 링크 간이 검사 450건 통과(최종 작업 기록 추가 전 기준). 역사 원문 내부의 18개 참조는 보존한다.
- 관리 대상 Python 76개 구문 검사 통과. 변경 경로의 공백 오류 검사 통과.
- 실험·역사·기존 릴리스 자료 17,588개에 대한 작업 전후 SHA256 대조에서 의도적으로 갱신한
  `experiments/README.md` 외에는 차이가 없었다. 기존 사용자의 `experiments/ai-passthrough/README.md` 수정도 보존했다.

문서 검사 첫 시도는 같은 임시 사본에서 결과 디렉터리를 제외하는 CPU 검사와 겹쳐 링크 조회가 실패했다.
CPU 검사 종료·디렉터리 복구 후 문서 검사를 순차 실행해 통과했다. 저장소 파일 누락으로 인한 실패는 아니다.

CUDA 알고리즘과 Guest/broker/Worker 실행 코드는 변경하지 않았다. 최초 구조 정리 단계에서는
소스 바이트와 빌드 입력 경로만 검증했다. 이후 사용자가 이미지 재빌드·GPU 검증·GitHub push를
요청하여 아래 후속 검증을 진행했다. 향후 모든 환경에서 문제가 없음을 보장하는 검증은 아니다.

작업 로그·보존 대조·검증 사본 위치는 로컬 `.local/repository-optimization-20261105/`에 있다.
이번 적용에는 Device Plugin 구현을 포함하지 않는다.


## 이미지 재빌드·GPU 검증·GitHub 반영

검증 소스는 [`45f1318b`](https://github.com/WoogiBoogi1129/VMWeave-GPU/commit/45f1318b126aed3dee06908466ba1f638d9692c1)이며
이 커밋을 GitHub `main`에 push했다. 기존 사용자의 미커밋 수정과 미추적 자료는 포함하지 않았다.
기계 판독 가능한 결과와 바이너리 hash는 [validation.json](evidence/repository-maintenance-20261105/validation.json)에 있다.

| 검증 | 결과 |
|---|---|
| 로컬 이미지 | 변경 영향이 있는 Guest artifacts·Worker를 `Runtime.Containerfile`로 빌드, 성공 |
| 빌드 방식 | Docker daemon 권한이 없어 rootless Podman 사용. 공통 runtime을 소스에서 컴파일하고 두 번째 target에서 해당 stage 재사용 |
| 빌드 내 회귀 검사 | `test-shm-training.sh`, `run_cuda_mock.sh` 통과. Guest 패키지 9개 checksum 및 source revision 일치 |
| GitHub Docker 빌드 | [deployment-images](https://github.com/WoogiBoogi1129/VMWeave-GPU/actions/runs/41975479252): operator·helper·worker·guest-artifacts·hook 5종 통과 |
| 실제 GPU | HAMi 25% / 1,024 MiB 할당, seed 23·71·119·187의 4회 smoke 통과. 4,096-byte 왕복 복사 및 PTX 커널 합계 8,418회 결과 검증 |
| 실행 바이너리 | Canary 내부 실행 중 Worker의 `/proc/PID/exe` SHA256이 새 로컬 이미지에서 추출한 바이너리와 일치. HAMi library 로드 확인 |
| 정리 | Worker 종료 후 대상 GPU 0 MiB. UID를 확인하고 임시 Pod·ConfigMap 정상 삭제. 강제 삭제·finalizer 변경 없음 |

GitHub의 [정적 검사](https://github.com/WoogiBoogi1129/VMWeave-GPU/actions/runs/41975479295),
[CPU 제어 검사](https://github.com/WoogiBoogi1129/VMWeave-GPU/actions/runs/41975479457),
[차트 검사](https://github.com/WoogiBoogi1129/VMWeave-GPU/actions/runs/41975479249),
[문서 검사](https://github.com/WoogiBoogi1129/VMWeave-GPU/actions/runs/41975479424)도 통과했다.
이번 main workflow는 이미지를 빌드·검증하며 GHCR 게시 조건은 기존 `v*` 태그 정책을 유지한다.
새 릴리스 태그 생성이나 운영 이미지 교체는 수행하지 않았다. 변경 없는 HAMi·HAMi-DRA 이미지도 교체하지 않았다.

**GPU 검증의 범위**

기존 VMWeave Worker VMIs는 검증 시작 시 `Failed`, 관련 Channel은 `Draining`이었다.
이 VM들을 재시작하거나 복구하지 않고 `vmweave-test-b`의 임시 Pod에서 검사했다.
GPU가 없는 Guest 컨테이너에는 새 Guest library·Broker·smoke를, HAMi GPU를 할당받은 Worker
컨테이너에는 새 session Worker 바이너리를 복사했다. Pod의 기본 이미지는 기존 v0.5.8 Worker이다.
따라서 새 컨테이너 이미지 자체의 클러스터 배포 검증과도 구분한다.

실제 VM의 PCI BAR를 대신하는 [테스트 전용 어댑터](evidence/repository-maintenance-20261105/file-backed-guest.c)가
Guest library의 매핑 호출만 별도 공유 파일에 연결했다. CUDA 호출·공유 메모리 큐·Broker 세션·Worker·HAMi·물리 GPU 경로는 실제로 실행했다.
초기 sysfs fixture 방식은 컨테이너 생성·파일 접근 제한에 막혀 사용하지 않았으며, 보안 설정을 완화하지 않았다.
smoke 출력의 `Guest-SHM-HAMi-GPU` 문자열만으로 VM 검증을 주장하지 않는다.
VM 부팅, 실제 ivshmem PCI BAR, VM 내부 Kubernetes, Device Plugin, 성능 회귀 검증은 포함하지 않는다.

빌드 원본 로그와 canary 실행 자료는 로컬 `.local/repository-publication-20261105/`에 보관했다.
