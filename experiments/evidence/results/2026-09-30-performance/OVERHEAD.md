# N/T/S 경로 비교 — 완료한 첫 단계

2026-09-30 시작 실험의 N/T/S 15개 세션·105개 구간을 완료했습니다. 경로별 독립 반복은 5회입니다. 단일 VM 상한·다중 VM 실험은 이어서 진행하며, 이 문서는 경로 비교 단계의 고정 결과입니다.

N은 직접 CUDA+HAMi, T는 Flyt TCP/RPC+MPS, S는 VMWeave SHM+HAMi입니다. 8개 호출·전송 지표 모두 S의 평균 지연이 T보다 컸습니다. 이 비교에는 정책과 실행기 차이도 포함됩니다.

| 지표 | N | T | S |
|---|---:|---:|---:|
| query-1048576 (µs) | 6.59 ± 1.29 | 716.73 ± 129.63 | 1,467.05 ± 13.59 |
| kernel-1048576 (µs) | 8.12 ± 0.50 | 1,769.03 ± 139.93 | 2,825.06 ± 20.76 |
| resident-2097152 (작업/초) | 113,190.43 ± 244.63 | 637.80 ± 130.84 | 355.19 ± 0.60 |
| transfer-2097152 (작업/초) | 3,638.83 ± 130.81 | 133.54 ± 1.42 | 64.15 ± 0.32 |

값은 실행별 평균의 평균 ± SD입니다. query는 cudaMemGetInfo, kernel은 launch+sync입니다. 2 MiB resident/transfer의 내부 반복은 64회이며, 후속 이용률 상한 시험의 긴 커널과 서로 다른 작업입니다.

![호출·전송 지연](figures/path-latency.png)

![경로별 처리량](figures/path-throughput.png)

[검증 기록](overhead-validation.json) · [전체 수치](analysis/overhead.csv) · [원시 실행 자료](runs/) · [실제 Grafana 캡처](captures/) · [실행 코드와 계획](../../../performance/README.md)

벤치마크가 각 구간의 전체 출력을 검산했습니다. 별도 검증기는 원시 표본 건수·검산 성공 기록·시각 연속성·관측된 GPU 프로세스·정상 회수를 대조했습니다. N/T/S의 개별 지연은 CSV로 보존하며 Grafana의 last-operation-latency 패널은 후속 단일·공유 부하 시험에서만 채워집니다.
