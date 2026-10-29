# 2026-10-22 SGEMM 비교 — 공개 자료 범위

이 디렉터리는 [기존 실험 보고서](REPORT.md)의 **선별 공개 묶음**이다.
2026-10-29 내부 Kubernetes 처리량과의 [비교 보고서](../../../nested-k8s-gpu/results/20261029-performance-comparison/REPORT.md)에서
인용하는 수치·조건을 저장소만으로 확인할 수 있도록 공개했다. GPU 실험을 새로 실행한 결과가 아니다.

- [측정 CSV](measurements.csv), [통계·정확성 판정](summary.json), [조건·버전](manifest.json), [선택 규칙 결과](selection.json).
- [실행 식별 검증](identity-validation.json), [서비스 관측 요약](continuity-summary.json), [자원 복구 결과](cleanup.json).
- [SGEMM 측정 소스](bench.py), [탐색 그래프](exploration.png), [별도 확인 3쌍 그래프](formal-pairs.png).
- correctness/explore/b1/b2/b3/diagnostic 아래 `result.json`: 기존 개별 실행의 수치·설정·검산 메타데이터.

원본 보고서와 인용 파일은 기존 바이트를 유지했다. 전체 로컬 묶음은 약 6.25GB이며,
대용량 출력 배열 `tensors.pt`, 전체 GPU/CPU 시계열·명령 감사·환경 전환 로그와 환경 전용 runner는
이번 공개에 포함하지 않았다. 보고서에서 언급한 모든 로컬 자료가 GitHub에 있다는 의미는 아니다.
공개 `bench.py`는 당시 실행 소스이며 별도 로컬 준비물이 필요한 GPU 재실행 절차를 대체하지 않는다.

**공개된 파일만 검증하려면** 저장소 루트에서 다음을 실행한다.

```bash
(cd experiments/ai-passthrough/results/20261022-sgemm-bestcase && sha256sum -c PUBLIC-SHA256SUMS)
```

`PUBLIC-SHA256SUMS`가 이번 공개 범위다. 기존 `SHA256SUMS`는 **비공개 로컬 파일을 포함하는 전체 실행 목록**으로
출처 확인을 위해 원본 그대로 보존했다. 새 clone에서 기존 전체 목록을 검증하면 누락 파일이 보고되는 것이 정상이다.
전체 출력의 재검산까지 가능한 공개 묶음으로 표현하지 않는다.
