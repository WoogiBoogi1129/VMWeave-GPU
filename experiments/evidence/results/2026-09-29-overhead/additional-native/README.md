# 중단 시점까지 완료된 추가 직접 실행

사용자가 현재까지 결과만 공개하도록 요청한 시점에 `r4-N`의 6개 측정 구간은
모두 정상 종료·검산을 마친 상태였다. 중단은 결과 파일의 공개용 gzip 압축 중에
발생했다. 원본 CSV와 전체 출력은 이미 보존되어 있어 그대로 다시 압축했다.
새 측정이나 표본 수정은 하지 않았다(`r4-N/export-recovery.json`).

조회, 작은 커널, 4 KiB/4 MiB 복사, resident/transfer 각 1개 구간이다.
대응하는 r4-T/S와 r5/r6는 실행하지 않았다. 이 세션은 N/T/S 각 3회인 본 비교표에
합치지 않으며, 완료된 관측값을 누락하지 않도록 원본·요약 CSV·검산을 별도로 제공한다.
`aggregate-summary.csv`의 n=1, 표준편차 0은 반복 간 변동성이 검증됐다는 뜻이 아니다.

- `r4-N/`: 실행 로그, 실제 정책, 원본 표본·전체 출력, 회수 기록.
- `validation.json`: 모든 표본 수와 출력 원소의 재검증.
- `latency-summary.csv`, `window-summary.csv`, `cpu-summary.csv`: 실제 추가 관측값.
- `clock-alignment-audit.json`: 호스트 모니터링과의 근사 시각 대응.
