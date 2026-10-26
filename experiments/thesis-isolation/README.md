# 2026-10-12~14 격리성 실험

[최종 보고서](report.md) · [선별 원시 증거](evidence/20261013/raw-evidence.tar.gz)

E1 및 단계별 승인된 성능 실험 P를 기록한다. E2는 40회 완료했으나 GPU 교차 접근 미검증으로 INCONCLUSIVE이며 E3는 시험 범위에서 10/10 PASS이며 E4도 시험 범위에서 실행기 10/10 PASS다. 시간 관측 한계는 보고서를 참조한다. `results/`는 로컬 전체 원본이며 공개 증거는 `evidence/`에 선별한다.

2026-10-14 보완: E2 API 예비 검증 및 확대 부하 30구간 완료. [보완 비교](evidence/20261014-supplement/comparison.json). E2 GPU 경로와 E4 시간 보완의 한계는 보고서에 유지한다.

기존 P와 확대 부하 P는 각각 기준 워크로드 단독 실행과 상대 VM 부하 동시 실행을 포함한다. 관측 MLP의 출력은 CPU 기준값과 비교했으며 두 캠페인 각각 381,945건 / 381,011건의 정상 완료에서 오류·결과 불일치가 없었다. 이 증거를 활용하며 같은 정상 실행 시험을 중복하지 않는다. 모든 워크로드의 무간섭이나 제품 전체의 데이터 접근 격리 보장으로 해석하지 않는다.

추가 완료 증거:

- [VM·Worker 계측 및 자기 접근](evidence/20261014-boundary-own/result.json): 자기 커널 6회, 양단 요청 64개 연결.
- [등록 포인터 교차 요청](evidence/20261014-boundary-cross/analysis.json): 4건 모두 Guest 제출 전 거절 확정.
- [Native CUDA 대조군 준비](evidence/20261014-native-prepare/analysis.json): 자기 커널 6회, 버퍼 검사 18회 불일치 0.
- [Native 교차 접근 예비 시험](evidence/20261014-native-peer/analysis.json): 4조건 실제 제출 후 동기화 오류 700, 상대 버퍼 검사 72회 불일치 0.

각 디렉터리의 `raw-evidence.tar.gz`와 `raw-sha256.json`에 선별 원시 자료와 해시를 보존한다. [계측·재현 도구 설명](instrumentation/README.md)에 환경 차이와 분석 명령을 설명한다. 분석기는 원시 자료를 검사하며 GPU를 실행하지 않는다. 재실행기와 구분한다. Native 보완은 제품 Guest/Worker 경로를 거치지 않으며 학습용 제품 경로의 추가 경계 시험은 미실행이다.


## 2026-10-26 Flyt MPS 비교 시도 — 측정 미완료

[비교 및 초기화 실패 보고서](evidence/20261026-flyt-mps-comparison/REPORT.md) · [HTML 보고서](evidence/20261026-flyt-mps-comparison/REPORT.html) · [그래프](evidence/20261026-flyt-mps-comparison/figures/) · [실행 계획](config/flyt-mps-comparison-plan-20261026.md)

기존 VMWeave의 원/확대 성능 결과를 재집계했다. 신규 Flyt는 PyTorch import 오류 및 대체 로딩 설정의 초기화 timeout으로 유효 측정 0구간이며, Flyt 감소율과 시스템 간 차이는 N/A다. 두 VM 동시 MLP 실행이나 성능 우열을 검증한 결과가 아니다. 시험 자원은 회수했다.

재집계·보고서/그래프 생성(GPU 실행 없음): `python3 experiments/thesis-isolation/runner/analyze_flyt_mps_comparison.py`. 의존성은 `matplotlib==3.9.4`, `Markdown==3.10.2`다. 초기화 진단 재실행 도구는 `runner/flyt_mps_initialization.py --help`를 참조한다. 이 도구는 사전 준비한 시험 VM과 로컬 SSH 설정이 필요하며, 자동으로 클러스터를 구성하거나 처리량을 측정하지 않는다.


## Flyt MPS 호환성 복구 및 신규 비교 (2026-10-26)

- [호환성 복구 보고서](evidence/20261026-flyt-compatibility/REPORT.md): 기존 VMWeave 패키징을 보존한 독립 Flyt 시험 패치, 검증 근거와 비이동 빌드의 제한.
- [처리량 비교 보고서·그래프](evidence/20261026-flyt-mps-recovered/REPORT.md): 신규 Flyt와 기존 VMWeave의 반복별 처리량 감소율, 방향별 결과, 절대 처리량 및 실제 부하량. 결과 확인 후 기존 메모리 부하 조건을 제외한 3개 조건의 선택적 비교이며, 전체 4개 조건 집계와 원시 기록은 보존한다. SHM·관측 시간·웜업·패치 및 종료 확인 절차의 차이를 명시한다.
- 재집계: `python3 experiments/thesis-isolation/runner/analyze_flyt_mps_recovered.py` (GPU/클러스터 접근 없음).
- [승인된 복구 계획과 실행 기록](config/flyt-compatibility-recovery-plan-20261026.md). 기존 초기화 실패 보고서는 당시 결과로 보존한다.
