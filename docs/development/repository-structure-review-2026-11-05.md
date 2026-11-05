# Device Plugin 개발 전 저장소 구조 검토

검토일: **2026-11-05 KST**. 기준 저장소는 `WoogiBoogi1129/VMWeave-GPU`,
기준 커밋은 `223468c9afc270abe9bb935b08b3244f4481bcc1`이다.
검토 시 `git ls-remote`로 GitHub 기본 브랜치 HEAD와 `main`이 이 커밋을 가리키는 것을 확인했다.

**판정: 최상위 구조는 유지하되, 최신 정보의 진입점·실험 자료 의존·CI 범위를 먼저 정리하는 것이 적절하다.**
Device Plugin을 추가하기 위해 기존 소스나 증거 전체를 재배치할 필요는 없다.
저장소 용량의 대부분은 실험 자료이며, Plugin의 저장소 분리 여부와 증거 보관 정책은 별도 판단이다.
이번 작업은 검토 문서와 로컬 집계 자료만 추가했다. 기존 파일 이동·삭제·내용 수정,
커밋·push·클러스터 조작은 수행하지 않았다.

**검토 범위와 방법**

- `main`의 전체 17,958개 추적 파일을 `git ls-tree -r -l -z`로 조사했다. 경로·크기·blob ID·중복을 집계했다.
- 원격 23개 브랜치와 12개 태그, 총 35개 ref 끝점의 트리도 전수 집계했다. 합집합은 18,219개 경로이며,
  이 중 261개는 현재 `main`에 없는 역사 경로다. 이는 끝점의 경로 합집합이지 전체 Git 이력의 파일 버전 수가 아니다.
- 현재 소스·빌드·배포·테스트·CI·문서 진입점의 참조 관계를 검토했다. Markdown 263개의 일반 상대 inline 링크를 검사했다.
- `git archive`로 커밋된 파일만 임시 디렉터리에 추출하고 기존 구조 검사와 문서 빌드를 실행했다.
- 작업 트리에는 기존 수정 1개와 미추적 파일 2,282개가 있었다. 이를 GitHub 등록 자료로 집계하지 않았다.
  특히 `docs/evaluation/2026-11-02-paper-readiness-review.md`와 그 CSV는 로컬 전용이므로 이 검토의 공개 근거에서 제외했다.
- 과거 각 브랜치·태그의 내용 전부를 의미적으로 재검증하거나 모든 실험을 재실행한 것은 아니다.
  GitHub Releases 첨부 파일, Packages 이미지 레이어, Actions artifact, Issues/Wiki는 Git 디렉터리 분석 대상에 포함하지 않았다.

원시 집계는 로컬 `.local/repository-review-20261105/`에 보존했다.
`files.csv`는 전체 파일 목록, `refs.csv`는 ref별 규모, `summary.json`은 디렉터리·대형 파일·중복 통계,
`relative-link-candidates.json`은 누락 링크 후보, `validation.json`은 검증 범위다.
이 디렉터리는 기존 ignore 정책에 따라 Git에 포함하지 않는다.

**전체 디렉터리 규모와 역할**

아래 용량은 현재 트리에 있는 파일의 Git blob 크기를 경로별로 합산한 값이다.
디스크 블록 사용량, 압축된 clone 전송량, 전체 이력 저장 용량과 다르다. MiB는 1,048,576 bytes다.

| 경로 | 파일 수 | MiB | 역할·판정 |
|---|---:|---:|---|
| `experiments/` | 17,250 | 1,237.792 | 실행기·계획·보고서·원본 결과. 탐색·증거 보존 정책 개선의 우선 대상 |
| `legacy/` | 257 | 1.178 | 이전 RPC 구현·역사 문서. 보존 유지 |
| `runtime/` | 86 | 0.365 | SHM 실행 경로와 HAMi/HAMi DRA 패치. 현재 경계 유지 |
| `docs/` | 82 | 0.310 | 현재 문서·과거 주소 안내. 최신 정보와 색인 정합성 보완 |
| `operator/` | 35 | 0.205 | 중앙 Go Operator·API·스키마·테스트. 독립 모듈 구조 유지 |
| `deploy/` | 97 | 0.191 | 예제·release lock·릴리스 증거·구 API 스키마. 용도별 안내 보완 |
| `tests/` | 45 | 0.170 | CPU·통합·배포·runtime 검증. 실험 결과 fixture 의존을 명시 |
| `scripts/` | 52 | 0.168 | 빌드·설치·운영·문서 검증. 현재·구 API 진입점 구분 |
| `charts/` | 21 | 0.095 | 현 VMWeave와 구 Flyt chart. 복제 CRD는 검사되는 의도적 복제 |
| 루트 파일 | 12 | 0.016 | README·개발/보안/라이선스·빌드·버전·ignore 정책 |
| `images/` | 12 | 0.013 | 현 VMWeave·HAMi·구 Flyt 이미지 정의 |
| `.github/` | 7 | 0.012 | 빌드·검증·배포 workflow. 의존 파일과 실행 범위 정합성 보완 |
| `artifacts/` | 1 | <0.001 | 로컬 산출물 안내만 추적 |
| `results/` | 1 | <0.001 | `reference/README.md`만 추적 |
| **합계** | **17,958** | **1,240.515** | **1,300,774,168 bytes** |

실험 자료는 파일 수의 **96.06%**, 용량의 **99.78%**다.
`experiments/`를 제외한 모든 추적 파일의 합계는 **2,855,332 bytes, 약 2.72 MiB**다.
핵심 코드 디렉터리가 과도하게 큰 상황은 아니다.

로컬 Git object pack 합계는 약 670.37 MiB였지만, 이 값에는 해당 clone이 가진 이력이 포함된다.
이를 GitHub 저장소 전체 크기나 새 clone의 다운로드 크기로 사용하지 않는다.
동일 blob이 여러 경로에 존재하는 그룹은 455개, 경로별 중복 용량은 약 18.31 MiB다.
Git의 동일 blob 저장은 공유되므로 중복 경로를 지운 만큼 저장소 전송량이 줄어든다고 볼 수 없다.
관측 전후의 동일 JSON이나 반복 실험 출력은 연구 근거일 수 있어 일괄 중복 제거 대상도 아니다.

**실험 디렉터리 23개의 구성**

| 디렉터리 | 파일 수 | MiB | 현재 형태 |
|---|---:|---:|---|
| `evidence/` | 8,054 | 1,076.109 | 공용처럼 사용되는 실행 도구·tests와 날짜별 results가 함께 있음 |
| `training-threeway/` | 3,746 | 45.764 | 루트 실행기·분석기·검증기와 results |
| `thesis-isolation/` | 489 | 43.617 | config·runner·evidence |
| `ai-passthrough/` | 3,217 | 25.819 | plans·runner·results |
| `sm-core-limit/` | 433 | 15.391 | runner·evidence·보고서 |
| `diagnostics/` | 46 | 13.538 | 날짜·주제별 진단 자료 |
| `nested-k8s-gpu/` | 671 | 9.061 | runner·workloads·lab·throughput·transfer-app·results |
| `vram-accounting/` | 403 | 7.464 | 루트 실행기·분석기와 results·evidence |
| `pytorch-smoke/` | 26 | 0.463 | 실행기와 results·evidence |
| `h2d-diagnosis/` | 50 | 0.150 | 진단 실행기·분석 도구 |
| `performance/` | 33 | 0.148 | 실행·관측·복구·분석 도구 |
| `system-comparison/` | 25 | 0.096 | 실행·관측·분석 도구 |
| `shm-first-bundle/` | 23 | 0.086 | 최적화 실험 실행·빌드·검증 도구 |
| `k8s-gpu-pod/` | 5 | 0.026 | 초기 VM 내부 Pod 실험 자료 |
| `dra-smoke/` | 11 | 0.017 | DRA smoke와 results |
| `operator/` | 2 | 0.015 | Operator 검증 기록 |
| `channel-controller/` | 3 | 0.011 | 단계별 설계·버전 기록 |
| `rpc-removal/` | 2 | 0.004 | 단계별 설계·버전 기록 |
| `shm-lifecycle/` | 2 | 0.003 | 단계별 설계·버전 기록 |
| `shm-cuda-core/` | 2 | 0.002 | 단계별 설계·버전 기록 |
| `shm-compatibility/` | 2 | 0.002 | 단계별 설계·버전 기록 |
| `vm-shm-channel/` | 2 | 0.002 | 단계별 설계·버전 기록 |
| `shm-async/` | 2 | 0.002 | 단계별 설계·버전 기록 |

위 23개 디렉터리에 `experiments/README.md` 한 파일을 더하면 17,250개다.

새 실험에는 `README.md`(목적·상태·실행 진입점), `runner/`, `workloads/`, `results/<run-id>/` 같은 공통 규칙을 적용한다.
기존 실험은 체크섬 목록이 runner와 소스까지 포함할 수 있으므로 규칙에 맞춰 일괄 이동하지 않는다.
결과가 `results/`와 `evidence/` 중 어디에 있느냐만으로 공개 상태나 신뢰성을 판단하지 않고 실험별 색인에 명시한다.

**우선순위 1: 최신 버전 안내와 버전 기준 정합성**

`README.md` 39행과 `docs/getting-started/portable-deployment.md` 30행은 최신 버전을 v0.5.2로 안내한다.
반면 `charts/vmweave-operator/Chart.yaml`은 0.5.8이며 v0.5.8의 공개·배포 기록도 등록되어 있다.
`versions.lock.yaml`의 `deployment.chartVersion`은 0.5.7이다.
`docs/overview/status.md`의 마지막 수정은 10월 1일인데, 평가 진입점에는 11월 학습 실험까지 추가되어 있다.
링크 대상이 존재하는 것만으로 현재 권장 절차와 역사적 검증 범위가 명확해지지는 않는다.

권장 대응은 현재 릴리스 색인을 하나 정하고 README·설치 진입점·MkDocs nav에서 참조하는 것이다.
과거 릴리스의 본문·digest는 유지하고 구버전임을 표시하면서 후속 버전 진입점을 제공한다.
Operator/chart와 Guest/Worker는 서로 다른 버전일 수 있으므로 모든 구성 요소를 같은 태그로 기계적으로 변경하지 않는다.
현행 chart version과 lock의 대응은 CI에서 검사한다.

`mkdocs.yml`은 v0.5.7과 v0.5.4를 nav에 표시하지만 v0.5.8은 미등록 상태다.
`docs/evaluation/catalog.md`에도 최근 주요 campaign이 모두 반영되어 있지 않다.
`experiments/README.md`의 나머지 디렉터리를 SHM 전환 당시 기록으로 설명하는 문구는 현재 23개 디렉터리를 충분히 설명하지 못한다.
기존 [구조 안내](repository.md)의 3,503개 파일·약 319 MB는 과거 커밋의 기록으로는 맞지만 현재 개요와 구분할 필요가 있다.

태그 목록에는 구 Flyt PoC의 `v1.0.0`(2026-08-24)도 있다.
단순히 가장 큰 semver를 현재 VMWeave 릴리스로 안내하지 않는다. 역사 태그를 삭제하거나 옮길 필요는 없다.

**우선순위 1: 배포 코드와 실험 자료의 의존 명시·축소**

현행 `images/vmweave/Runtime.Containerfile` 18행은
`experiments/evidence/guest_gpu_smoke.c`를 COPY하여 Guest 배포물에 포함한다.
`scripts/run-evidence-smoke.py`도 실험 디렉터리의 여러 probe를 참조한다.
`tests/control/test_stage1_evidence.py`와 `test_stage2_evidence.py`는 과거 결과의 JSON·trace를 fixture로 읽는다.
따라서 `experiments/`를 외부 저장소로 통째로 옮기면 배포물 빌드나 CPU 테스트가 깨진다.

배포용 smoke를 `tools/guest-smoke/`처럼 책임이 명확한 위치로 독립시키는 것이 좋다.
기존 파일이 체크섬 대상인지 확인한 후, 원본을 보전하면서 새 소스의 출처를 기록하거나 참조를 갱신한다.
이때 Containerfile, workflow, smoke 실행기, 문서, 해시 대상을 함께 확인해야 한다.
과거 결과를 쓰는 테스트는 출처·hash를 가진 최소 fixture를 `tests/fixtures/`에 두거나 필요한 증거 파일 집합을 명시해 가져오도록 한다.
출처 없는 임의 데이터로 대체하지 않는다.

이 의존 정리는 별도 개선 항목이며 첫 Plugin 구현을 전면 중단시킬 조건은 아니다.
Plugin 자체의 빌드·테스트에서 과거 실험 전체를 요구하지 않는 경계를 먼저 지키면 된다.

**우선순위 1: CI 실행 범위와 실제 빌드 입력의 대응**

- `control-plane.yml`과 `deployment-chart.yml`은 PR 시 path 제한이 없어 실험 결과만 바뀌어도 실행 대상이 된다.
  불필요한 실행 가능성이 있지만 이번에 실제 Actions 시간·비용을 측정한 것은 아니다.
- `images.yml`의 paths에는 Runtime.Containerfile이 COPY하는 `tests/integration/**`,
  `tests/path_optimization/**`, `scripts/test-shm-training.sh`가 없다.
  이 파일들만 바뀐 PR에서는 해당 이미지 빌드 workflow의 검증이 시작되지 않는 구성이다.
- `static.yml`의 Python 구문 검사는 `glob('*.py')`를 사용해 지정한 root 바로 아래만 검사한다.
  하위 디렉터리의 Operator용 script 등은 이 검사 대상이 아니므로 전체 Python 구문 검사로 해석하지 않는다.

Plugin workflow는 독립시키고 본체·chart·Containerfile·공유 계약·검증 코드 변경을 대상으로 한다.
기존 CI의 path 제한은 의존 목록을 기준으로 적용하고 필수 체크가 skip 상태로 대기하지 않는지도 확인한다.
GitHub의 [path filter 규칙](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onpushpull_requestpull_request_targetpathspaths-ignore)에 따라,
필요하면 항상 실행되는 통합 체크와 job별 실행 여부 판정을 조합한다.

**우선순위 2: 실험 원본 증가 관리와 탐색 색인**

최대 파일은 `experiments/evidence/results/2026-09-30-performance/commands.jsonl`로
79,809,786 bytes(약 76.11 MiB)다. 50 MiB 초과 경고 대상 크기지만 일반 Git 파일의 100 MiB 제한을 넘지는 않는다.
GitHub는 큰 배포물을 Release에 제공하는 방법도 안내한다.
[GitHub 공식 설명](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)

기존 [증거 보존 정책](../evaluation/artifacts.md)도 새로운 대용량 결과를 Release 등에 저장하는 방향을 제시한다.
먼저 이를 구체적인 검토 규칙으로 만든다. 새 대용량 로그·센서 시계열·영상은 저장 위치를 검토하고,
Git에는 보고서·재현 소스·요약·checksum·bytes·다운로드 URL·기준 커밋을 남긴다.
저장 위치의 공개 범위·보존·다운로드 후 hash 확인도 검증한다. 단기 Actions artifact만 영구 참조처로 사용하지 않는다.

디렉터리 이름 변경이나 새 커밋에서의 삭제만으로 과거 Git object는 제거되지 않는다.
따라서 전체 이동이나 LFS 도입만으로 clone 용량이 곧바로 줄어든다고 주장하지 않는다.
기존 인용과 hash를 보존하고 새 자료의 추가 방식부터 개선한다. 이력 재작성은 이번 권장 범위에 포함하지 않는다.

개발자용으로 partial clone과 sparse checkout 안내도 검토할 수 있다.
`--filter=blob:none`은 필요할 때 blob을 가져오며, 전체 트리를 checkout하면 현재 파일은 결국 가져오게 된다.
효과를 얻으려면 선택 checkout과 위의 fixture·smoke 의존 정리를 함께 적용해야 한다.
[Git 공식 clone 옵션](https://git-scm.com/docs/git-clone)

**우선순위 2: 현행 자료와 역사 자료의 역할 표시**

`legacy/`는 명시적으로 분리되어 있으나 구 `charts/flyt-control-plane`, `images/flyt`,
`deploy/shm`, Python controller는 현행 디렉터리에도 남아 있다.
그러나 현행 helper도 `runtime/shm/control/`을 쓰며 CI도 구 chart를 검사하므로 Flyt라는 이름만으로 이동 대상을 정하지 않는다.
`operator/internal/engine/reclaim_helper.py`는 Go에 embed되는 현행 회수 처리이며,
`runtime/shm/control/reclaim.py`와 책임·내용이 같은 중복 파일로 취급하면 안 된다.

각 영역에 현재 배포 대상·호환/재현용·실험 전용의 대응표를 두고 이동은 참조 조사 후 작은 변경으로 수행한다.
`charts/`의 CRD 복사본은 기존 일치 검사가 있는 의도적인 중복이므로 삭제하지 않는다.
루트 `artifacts/`와 `results/`는 작은 안내 파일만 있어 용량을 줄이려고 제거할 실익이 없다.

**우선순위 2: 문서 링크와 증거 바이트 보존 보완**

커밋된 Markdown 263개에서 일반 상대 inline 링크 1,813건을 간이 검사해
현재 Git 트리에 대상이 없는 후보 19건을 얻었다. 내역은 `legacy/` 13건, `experiments/` 5건, `runtime/` 1건이다.
이 검사는 완전한 Markdown parser가 아니며 외부 URL·anchor·코드 내 참조까지 검사하지 않았다.

현행 runtime에서는 `runtime/shm/cuda-dispatch/README.md` 6행의
`../evidence/IMPLEMENTATION_AND_VALIDATION_2026-09-22.md`가
`runtime/shm/evidence/...`로 해석되어 대상이 없다. 수정 가치가 있는 현행 안내의 사례다.
같은 README에 초기 단계의 미실행 설명도 남아 있어 현재 구현 안내와 당시 기록을 구분하는 것이 좋다.
역사적 결과 내부의 링크는 원본을 조용히 고치기보다 외부 안내·경로 대응표로 보완하는 방법을 우선한다.

MkDocs build 통과와 저장소 전체 Markdown의 링크 정상 여부는 별개다.
`scripts/docs_hooks.py`는 docs에서 다른 영역으로 향하는 링크 대상의 존재를 검사하지만 대상 Markdown 내부를 재귀 검사하지 않는다.
일부 구 결과는 고정 커밋으로 링크하고 나머지는 `main`으로 변환한다. 앞으로 연구 근거로 인용하는 색인에는
실험별 확정 커밋과 hash를 명시한다.

`nested-k8s-gpu/`에는 자체 `.gitattributes`가 있으며 검사한 SGEMM 보고서는 `text: unset`이었다.
반면 checksum을 가진 `training-threeway/results/20261102/REPORT.md`는 `text: unspecified`였다.
현재 손상되었다는 뜻은 아니지만 checkout 환경의 개행 변환을 피하는 규칙을 hash 대상에 맞춰 보완할 필요가 있다.
새 실험 템플릿에는 checksum 대상과 속성 규칙 확인을 포함한다.

**Plugin 추가 시 권장 구조**

```text
VMWeave-GPU/
├── operator/                         # 외부 클러스터의 중앙 Operator
├── runtime/shm/                      # 기존 Guest·broker·Worker
├── runtime/hami*/                    # 외부 GPU backend용 patch
├── integrations/
│   └── kubernetes-device-plugin/     # 신설: 독립 Go module·내부 테스트
├── charts/vmweave-device-plugin/     # 신설: VM 내부 Kubernetes 선택 설치
├── images/vmweave/                   # Plugin 독립 Containerfile 추가
├── tools/guest-smoke/                # 후속 후보: 배포용 probe와 실험 원본 구분
├── tests/fixtures/                   # 후속 후보: 출처가 있는 최소 fixture
├── deploy/                          # 현행 예제·release lock·릴리스 검증 기록
├── experiments/                     # 기존 원본 유지, 새 campaign 규칙 적용
├── docs/                            # 관리자·Guest 사용자·Plugin 사용자 진입점
└── legacy/                          # 역사 구현·문서
```

위 구조는 제안이며 이번에 해당 디렉터리를 만든 것은 아니다.
Plugin 본 구현을 `runtime/shm/control/`이나 `experiments/nested-k8s-gpu/`에 넣지 않는다.
전자는 기존 Guest/runtime, 후자는 특정 실험과 보존 증거를 관리하기 때문이다.
외부 Operator와 내부 Plugin의 설치를 독립시킨다.
Plugin 독립 태그는 예를 들어 `device-plugin-v0.1.0`으로 두어 현재 `v*`로 실행되는 본체 릴리스 workflow와 충돌하지 않게 한다.
본체와 Plugin의 대응은 호환 표로 관리하고 같은 버전 번호를 강제하지 않는다.

**실행 순서와 완료 판단**

| 순서 | 대응 | 완료 판단 |
|---|---|---|
| 1 | 현행 릴리스 색인, README·nav·chart lock 정합성, 실험 색인 갱신 | 신규 사용자가 현행 버전과 역사 자료를 구분할 수 있음 |
| 2 | Plugin 책임·독립 module·배포물·CI·호환 표 방침 확정 | 기존 Operator/runtime 배포와 독립적으로 검증·선택 설치 가능 |
| 3 | Plugin 구현과 병행해 smoke·fixture 의존 정리 | 필요한 최소 소스·fixture로 해당 build/test가 동작함 |
| 4 | 새 실험의 저장·checksum·색인 규칙 적용 | 공통 진입점에서 찾고 원본을 내려받아 대조할 수 있음 |
| 5 | 필요성을 확인한 구 진입점만 단계적으로 정리 | 참조·CI·배포물·원본 hash가 유지됨 |

대규모 폴더 이동, 과거 결과 재배치, 전체 이력 재작성을 Plugin 개발의 전제로 두지 않는다.
향후 별도 저장 위치를 검토할 때도 용량 대책의 주 대상은 실험 원본이며 Plugin 소스 분리는 유지보수 관점에서 결정한다.

**이번 검증 결과**

| 검사 | 결과 |
|---|---|
| 원격 HEAD·main과 분석 커밋 일치 | PASS |
| 원격 35개 ref 트리 조회 | 모두 성공 |
| `scripts/check-repository.py` | PASS: 구 CRD 복사본·이동된 코드 참조·그림 hash |
| `operator/hack/check-crds.py` | PASS: 현행 API group·scope·chart 복사본 |
| `scripts/check-doc-contracts.py` | PASS: guide 24개·CLI 예제 23개·관리자/사용자 분담 |
| `mkdocs build --strict` | PASS. nav 미등록 페이지는 INFO로 출력 |
| `scripts/check-site.py` | PASS: HTML 77개·검색 항목 234개·로컬 링크·anchor |
| 전체 Markdown 간이 상대 링크 검사 | 1,813건 중 대상이 없는 후보 19건 |

위 수치는 분석 대상 커밋의 깨끗한 복사본에서 얻은 기준 결과다.
코드 변경, Docker build, GPU 실험, VM·Kubernetes 조작은 수행하지 않았다.
기존 검사 PASS가 최신 버전 안내의 의미적 정합성이나 모든 연구 자료의 링크까지 보장하는 것은 아니다.
