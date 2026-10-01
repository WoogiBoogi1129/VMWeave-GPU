# 모니터링 증거와 재조회

이번 실험을 위해 `vmweave-performance` namespace에 전용 Prometheus 3.5.0,
Grafana 12.0.2, NVIDIA DCGM Exporter `4.6.0-4.8.3-distroless`, node-exporter 1.9.1을
배포했습니다. 기존 GPU Operator exporter는 유지했습니다. HAMi exporter와
실제 작업 진행·VM/Worker CPU 카운터를 함께 수집했습니다.

## 보존 파일

- `setup.json`: 실제 설치 조건.
- 각 `../runs/*/telemetry.json`: 조회 식·UTC 범위·1초 step을 포함한 Prometheus 원본 응답.
- `cpu.jsonl`: 상위 Pod cgroup별 실제 CPU 누적 카운터. 하위 cgroup을 중복 합산하지 않음.
- `pmon.txt`: 실제 `nvidia-smi pmon` 출력. 시각은 호스트 Asia/Seoul이며 실제 간격이 요청한 1초보다 길 수 있음.
- `collectors.json`: 실험 수집 프로세스 PID와 명령.
- `performance.json`: 실제 Grafana dashboard JSON.
- `prometheus-during-experiments.yml`: 계측 중 scrape 설정.
- `prometheus.yml`: 실험 종료 후 보존용 scrape 설정.
- `../runs/*/grafana-annotations.json`: 실제 기록된 측정 이벤트의 dashboard annotation 반영 이력.
- `retained.json`, `kubernetes-resources.json`: 종료 후 서비스·Pod·건강 상태.
- `tsdb-snapshot.json`: 종료 시 생성한 로컬 TSDB snapshot 이름.

종료 이후 파일은 전체 실행·검증 후 생성합니다. 실험 중 snapshot과 최종 보존 상태를 혼동하지 않습니다.

## 종료 후 접속

최종 `retained.json`에서 서비스 생성과 정상 상태를 먼저 확인한 뒤 실행합니다.

```sh
kubectl -n vmweave-performance port-forward svc/perf-monitor 3000:3000 9090:9090
```

Grafana는 `http://127.0.0.1:3000/d/vmweave-performance/`에서 조회합니다.
대시보드는 anonymous Viewer이며, 관리자 비밀번호는 Kubernetes Secret으로 보존하고 공개하지 않습니다.
Prometheus는 `http://127.0.0.1:9090/`입니다. 캡처 옆 `.txt`의 실제 절대 UTC 범위를 선택합니다.
캡처 당시 Pod IP는 역사적 주소이므로 재접속에는 위 서비스를 사용합니다.

측정 완료 후 애플리케이션 exporter와 pmon만 종료합니다. 보존된 Prometheus는
DCGM·HAMi·node 세 대상을 계속 수집합니다. 현재 GPU가 idle이어도 과거 부하를
재실행한 것으로 해석하지 않습니다. 살아 있는 TSDB의 retention은 30일이고,
로컬 snapshot은 `gpu-4`의 `.local/performance-20260930/monitoring/prom-data/snapshots/`에
별도 보존합니다. GitHub에는 각 실험의 원본 조회 응답을 함께 남겨 live retention 이후에도 분석할 수 있습니다.

데이터와 도구는 이 testbed의 hostPath에 보존됩니다. 다른 노드로 자동 이전되는
고가용성 모니터링 구성을 의미하지 않습니다. 캡처는 실제 Grafana를 측정 후 조회한 화면입니다.
N/T/S 개별 지연은 원시 CSV를 사용하며, 해당 구간의 last-operation-latency 패널이
No data인 것은 지연 0을 뜻하지 않습니다.
