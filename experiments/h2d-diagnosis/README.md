# 16MiB H2D 지연 원인 분리 실험

2026-10-01 전체 시스템 비교의 TCP/RPC 7.7163ms, 개선 SHM 9.2713ms 차이
(+20.2%, 약 1.555ms)를 재현하고, SHM의 어느 작업을 바꾸면 실제 지연이 줄어드는지 검증한다.
TCP+MPS와 SHM+HAMi의 차이를 전송 매체만의 효과라고 주장하지 않는다.

[결과 보고서·원시 자료](../evidence/results/2026-10-05-h2d-diagnosis/README.md)를 함께 읽는다.
운영 `runtime/shm/`는 변경하지 않으며 계측·후보 구현은 별도 소스 복사본에서 빌드한다.

## 실제 실행 순서

1. `reanalyze_prior.py`: 이전 5회 CSV 재분석. 과거 copy와 sync는 합쳐져 있어 분해 불가능하다.
2. `prepare.py`, `setup_tcp.py`: 기존 digest·바이너리와 캠페인 전용 자원을 준비한다.
3. `make_diagnostic_source.py`, `build_diagnostic.py`: 진단 소스와 초기 후보 이미지 준비.
   실제 예비 버전별 patch·해시는 결과의 `build/`에 보존했다.
4. `run_candidates.py`, `run_direct_pilot.py`: 짧은 예비 탐색. 기존/재사용/pinned/unroll/chunk 및
   Guest staging 복사 제거를 비교했다. 예비 결과는 정식 통계에 합산하지 않는다.
5. 초기 주 비교의 사후 SHA256 수집 경합을 고친 뒤 `recover_collection.py`로
   T/S 모두를 새 이름으로 재시작했다. 종료 barrier는 모든 측정 뒤에만 동작한다.
   `freeze_main.py`, `run_main.py`: 기존 운영 바이너리로 4/8/12/16MiB T/S 각 5회 측정.
   초기 runner는 결과의 `build/main-runner-frozen.py`와 해시로 보존하며,
   최종 정식 비교는 `hd-main-v2-*`와 새 `protocol-main.json`을 기준으로 한다.
6. `prepare_followup.py`: 최종 계측 종료 처리 수정본과 metrics OFF 이미지, 공통 probe 빌드.
   `smoke_final.py`로 최종 바이너리의 정확성과 정상 종료를 확인한 뒤 후속 프로토콜을 고정한다.
7. `run_followup.py`: 원래/복사 제거 × 계측 ON/OFF 각 5회, 별도 CPU/NUMA 한 쌍.
   주요 16MiB 왕복은 60초, H2D 단독·작은 전송은 10초 보조 구간이다.
8. `analyze.py`, `analyze_cpu.py`, `summarize.py`, `validate.py`, `plot.py`, `report.py`:
   원시 자료 검증과 세션 단위 집계, 그림과 보고서 생성.

`run_baseline.py`는 과거 probe 그대로의 재실행 시도에 사용됐으나 측정 전 준비 실패로 끝났다.
`run_components.py`의 독립 추가 캠페인은 실행하지 않았다. BAR 구성요소는 후속 두 VM에 통합했다.
`run_diagnostic.py formal`의 초기 reuse/pinned 반복 계획도 실행한 정식 캠페인이 아니다.
실제로 완료한 이름·구간 수는 `validation.json`과 고정 프로토콜을 기준으로 한다.

## 데이터 분석 재현

GPU나 클러스터 접근 없이 저장소 루트에서 실행한다. Python 3.12로 실행했으며
그림은 NumPy 2.5.3·Matplotlib 3.9.4가 설치된 `.local/evidence-venv/bin/python`으로 생성했다. 대형 `.xz` 로그는 직접 읽는다.

```sh
python3 experiments/h2d-diagnosis/analyze.py
python3 experiments/h2d-diagnosis/analyze_cpu.py
python3 experiments/h2d-diagnosis/summarize.py
python3 experiments/h2d-diagnosis/validate.py
python3 experiments/h2d-diagnosis/plot.py
python3 experiments/h2d-diagnosis/report.py
```

실험 호스트에서 분석 부하를 분리하기 위해 일부 스크립트는 CPU 48–51을 사용한다.
다른 장비에서는 사용 가능한 CPU 집합으로 바꾸거나 affinity 설정을 해제한다.
로그 SHA256은 결과의 `SHA256SUMS`, 압축 전 해시는 `archive-manifest.json`으로 확인한다.
보고서 재생성은 실험 결과가 모두 존재하고 검증을 통과한 뒤에만 가능하다.

## 진단 런타임 소스 재현

기준 커밋 `00cf878`의 `runtime/shm/`를 별도 작업 디렉터리에 복사하고,
그 디렉터리 안에서 `build/final-portable.patch`를 `patch -p1`로 적용한다.
새 파일을 포함한 소스 해시는 `build/portable-patches.json`에 있다.
`source_patch.py`는 실제 별도 소스에서 이 patch를 생성하고,
`test_portable.py`는 patch를 재적용해 해시와 ASan/UBSan 테스트를 검증한다.
운영 소스에 patch를 직접 적용하지 않는다.

빌드는 CUDA 개발 도구가 있는 `localhost/flyt-build:stage2-20260928` 환경에서
CMake Release로 수행했다. 실제 명령과 출력은 결과의 commands 로그에 보존한다.
이미지 이름만으로 같은 바이너리임을 추정하지 않고, 각 실행의 effective Guest hash,
실행 중 Worker hash, CUDA/HAMi 매핑·정책과 이미지 digest를 대조한다.
호스트별 이미지·GPU UUID·CPU 배치·Kubernetes namespace는 `common.py`와 프로토콜에 명시한다.
로컬 이미지와 현재 Operator가 필요한 전체 GPU 실행은 범용 한 줄 명령이 아니다.
새 캠페인에서는 BASE/OUT/이름을 바꿔 과거 결과와 충돌하지 않도록 한다.

## 계측과 후보

`HD_METRICS=1`은 thread-local bounded 메모리에 기록하고 종료 시 출력한다.
측정 루프에서 요청별 파일 쓰기를 하지 않으며 누락 카운터 0을 검사한다.
종료 dump 뒤의 늦은 기록은 거부한다. CUDA teardown 이후 Worker 성공 표식을 확인한다.
Guest 측정 구간의 H2D request ID로 각 endpoint 기록을 연결하며 서로 다른 시계를 빼지 않는다.

| 번호 | 구간 | 해석 |
|---|---|---|
| 1 | Guest 사용자 버퍼→staging | payload 복사; direct는 복사 없이 계측 경계 비용만 남음 |
| 2 | Guest→SHM | 대조군은 staging, direct는 사용자 payload에서 복사 |
| 3 | Worker private 입력 할당 | 할당 함수만 측정; 전체 malloc/free 수명 비용이 아님 |
| 4 | SHM→Worker private snapshot | 검증 경계를 유지한 payload 복사 |
| 5 | Guest exchange | submit·receive와 다른 구간을 포함하므로 합산 금지 |
| 6 | Worker dispatch | CUDA API 등을 포함하므로 합산 금지 |
| 7 | Worker response | 응답 준비·큐 게시 |
| 8 | Worker CUDA H2D API | CPU API 시간; 순수 DMA 시간이 아님 |
| 9 | Worker CUDA D2H API | CPU API 시간 |
| 10 | Worker CUDA sync API | CPU API 시간 |

`HD_VARIANT`는 진단 빌드에만 있다.

- `original`: 기존 복사 경로.
- `reuse`: 검증된 Worker private 입력 버퍼 재사용.
- `pinned`: 재사용 버퍼를 cudaHostAlloc/cudaFreeHost로 할당.
- `unroll`: volatile snapshot 64-byte loop unroll.
- `chunk`: Guest staging memcpy를 1MiB로 나눔.
- `direct`: Guest private header는 유지하고 사용자 payload를 SHM으로 직접 복사.
  동기 caller 입력 수명과 기존 mutex를 유지하며 Worker private snapshot/검증은 남긴다.
  CPU payload 복사 3→2회이며 GPU zero-copy가 아니다.

후속 정식 실험의 Worker는 모두 같은 최종 바이너리·`HD_VARIANT=original`이다.
Guest만 original/direct를 바꾸고 Worker의 metrics ON/OFF는 별도 이미지 환경 변수로 설정한다.

`probe.c`는 H2D copy/sync와 D2H copy/sync를 각각 보존한다.
결과 버퍼 전체 검산과 독립 SHA256 확인은 각 측정 구간 밖에서 수행한다.
`followup_probe.c`는 같은 작업을 호출하며 ON/OFF의 왕복/H2D 단독 순서를 맞춘다.
`map_probe.c`는 요청을 아직 시작하지 않은 채널의 payload 영역만 사용한다.
BAR 구성요소 결과는 end-to-end CUDA 성능이나 PAT cache policy의 인과 시험을 대체하지 않는다.

## 보존과 안전한 종료

SSH 키·Mongo 자격 증명·빌드 바이너리는 `.local/h2d-diagnosis-20261005`에만 둔다.
공개 전 `redact_evidence.py`로 자격 증명을 마스킹하고 별도 전체 검사를 한다.
실패한 실행과 제외 이유를 보존하며 같은 이름으로 측정을 덮어쓰지 않는다.
채널 Released 및 task UID를 확인한 자원만 정리한다.
이미지 저장/추출은 `/dev/shm` 임시 공간을 사용해 노드 디스크 압박 재발을 피한다.
