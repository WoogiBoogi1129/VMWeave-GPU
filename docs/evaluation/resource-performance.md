# 연산 이용률 상한·실행 경로·다중 VM 성능

2026-09-30에 시작한 새 campaign입니다. 현재 중앙 Go Operator와
`vmweave.io/v1alpha1`을 사용하며 과거 결과를 새 실행으로 계산하지 않습니다.

- [실행 계획과 재현 코드](../../experiments/performance/README.md)
- [고정한 측정 조건](../../experiments/evidence/results/2026-09-30-performance/protocol.json)

## 평가 범위

1. 호스트 직접 CUDA+HAMi, Flyt TCP/RPC+MPS, VMWeave SHM+HAMi 비교.
2. VM 하나에서 HAMi 이용률 상한 25/50/75/100에 따른 이용률·처리량·지연·완료 시간.
3. 50/50, 25/75 설정에서 다른 VM의 부하 시작·종료에 따른 변화.

100은 연산 제한 없는 기준이며 비활성 조건을 별도 본 실험으로 추가하지 않습니다.
이용률 상한을 물리 코어 고정 배분이나 처리량 비율 보장으로 해석하지 않습니다.
다중 VM 정상 상태 관측은 부하 변화 실험의 동시 실행 구간에 통합합니다.

## 관측과 기록

Prometheus·Grafana·전용 DCGM Exporter를 Kubernetes에 배포했습니다.
HAMi와 node-exporter, VM/Worker Pod cgroup CPU, 실제 GPU 프로세스 이용률도 수집합니다.
명령·출력·종료 코드·실제 터미널 세션을 보존하고, Grafana는 원시 시계열을
절대 UTC 범위로 조회하여 캡처합니다. 캡처는 측정 후 로그 검토임을 표시합니다.

## 완료한 결과와 진행 상태

N/T/S 15개 세션·105개 구간과 단일 VM 20개 세션·40개 구간을 완료했습니다.
다중 VM의 부하 시작·종료 실험은 진행 중입니다.

| 이용률 상한 | 평균 GPU 이용률 | 처리량 (작업/초, 평균 ± SD) | 사전 상한 기준 |
|---:|---:|---:|---|
| 25 | 84.39% | 80.61 ± 0.65 | 5/5회 위반 |
| 50 | 85.75% | 82.68 ± 0.38 | 5/5회 위반 |
| 75 | 87.22% | 83.24 ± 0.12 | 5/5회 위반 |
| 100 | 88.07% | 83.90 ± 0.13 | 제한 없는 기준 |

상한 기준은 중앙 90초 평균 이용률 ≤ 설정값+10%p, 유효 계측 ≥95%입니다.
이는 연구용 판정 기준입니다. 해당 GPU·설치된 HAMi 빌드·부하에서 이용률 상한 준수는 입증되지 않았습니다.
정책·라이브러리 매핑·실제 호출 경로를 확인했으며, 제어 경로의 영구 비활성을 단정하지 않습니다.

N/T/S의 8개 호출·전송 지표 모두 S 평균 지연이 T보다 컸습니다.
MPS/HAMi 정책과 실행기 차이가 포함되므로 전송 매체만의 효과로 해석하지 않습니다.

- [N/T/S 결과와 원본](../../experiments/evidence/results/2026-09-30-performance/OVERHEAD.md)
- [단일 VM 결과와 원본](../../experiments/evidence/results/2026-09-30-performance/SINGLE.md)
- [관측과 원인 분석의 범위](../../experiments/evidence/results/2026-09-30-performance/DIAGNOSTICS.md)

예비 실행은 본 실험 반복에 포함하지 않습니다. 계산 검산·실행 기록 검증 PASS는 상한 준수 PASS를 뜻하지 않습니다.
