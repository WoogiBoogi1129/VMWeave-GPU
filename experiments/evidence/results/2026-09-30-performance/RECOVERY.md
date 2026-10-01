# 공유 단계 중단과 재개

2026-10-01 08시대(KST) 확인 결과, 원래 공유 실행기의 프로세스가 존재하지 않았습니다.
정확한 종료 원인은 확인하지 못했습니다. 완료된 단계는 N/T/S 15세션, 단일 VM 20회,
공유 7쌍이었습니다. 여덟 번째 쌍의 마지막 기록은 워밍업 완료와 시작 대기였으며
측정 시작·완료 결과는 보존돼 있지 않았습니다. 두 VM은 이미 Halted, 채널은 Released였습니다.

- 원래 시도: `perf-d-r2-25-75-a`와 두 VM의 원본 디렉터리를 그대로 보존.
- 중단 메타데이터: [interruptions.json](interruptions.json), 실행별 `interruption.json`.
- 회수 상태: 실행별 `interruption-cleanup.json`. 이는 사후 관측이며 벤치마크 성공 기록이 아님.
- 대체 시도: `perf-d-r2-25-75-a-resume1`. 나머지 12쌍과 함께 수행.
- 기존 완료 7쌍은 재실행하지 않음. 측정 바이너리 해시·상한·워밍업·관측 시간은 유지.
- 재개 환경: [GPU 상태](resume1-gpu-before.txt), [소스·프로토콜](shared-resume1-source.json).
- 관리용 helper만 남은 실행과 정리를 감당하도록 수명을 갱신: [UID 기록](admin-renewal.json).

기존 상태 도구는 저장된 마지막 이벤트만으로 활성 실행을 표시할 수 있었습니다.
이제 실제 실행기 PID 존재와 로그 갱신 경과 시간을 함께 표시하며, 중단 시도는 따로 구분합니다.
재개는 `vmweave-performance-resume1.service`라는 사용자 systemd 서비스에서 실행합니다.
대화형 도구 세션과 수명을 분리했고 자동 재시작은 사용하지 않습니다.
실제 명령과 서비스 정보는 [resume1-supervisor.json](resume1-supervisor.json)에 있습니다.

```sh
systemctl --user show vmweave-performance-resume1.service \
  -p ActiveState -p SubState -p Result -p ExecMainStatus
python3 experiments/performance/status.py
```

서비스 시작은 완료 판정이 아닙니다. 전체 유효 반복·원시 표본·계산 검산 기록·시각·회수 검증은
최종 `validation.json`을 기준으로 합니다. 원래 중단 시도는 삭제하거나 성공으로 바꾸지 않습니다.
서로 다른 시간대에 수행한 두 실행 구간의 원본 시각도 그대로 남깁니다.

원래 대기 로그와 재개 사이에는 약 6시간의 공백이 있습니다. 각 쌍에서 GPU의 다른
프로세스 부재·모니터링 상태·VM 시각을 다시 확인했지만, 시간대별 환경 차이가
완전히 없었다고 보장하지는 않습니다. 실행별 값과 시각을 함께 보존해 반복 간
변동을 검토할 수 있도록 했습니다. 이 공백을 연속 실행 시간이나 GPU 작업 시간으로 합산하지 않습니다.
