# 모니터링 증거

- `observations.jsonl.xz`: 관측기의 원시 JSONL. 실제 UTC 시각, GPU 전체·프로세스 사용량, 실험별 마지막 API 상태, 해당 실험 Worker의 HAMi 행을 보존한다.
- `device/hami/requested/free/total/util/scrape.json.xz`: 실제 Prometheus `query_range` 응답. 조회식과 시간 범위는 `queries.json`에 있다.
- `physical.csv`: NVML CLI의 장치 전체와 프로세스 합. 호출은 원자적이지 않아 전환 구간 차이를 그대로 해석하지 않는다.
- `prometheus-tsdb.tar.xz`: 수집 종료 후 보존한 전용 Prometheus 데이터 디렉터리. 복구 시 전용 디렉터리에서 같은 버전 Prometheus를 실행하고, 빈 scrape 설정을 사용해 신규 데이터와 혼합하지 않는다.

Prometheus 3.5.0, Grafana 12.0.2. dashboard 원본은 `../../../dashboard.json`에 있다.
초기 exporter Content-Type 누락으로 일부 Prometheus scrape가 실패했다. 원시 관측은 별도로 남았으며, Grafana 캡처는 정상 수집 구간을 사용한다. 누락 표본을 합성하거나 보간하지 않았다.

Guest gauge는 이벤트 기반 최신 값이다. Channel 회수 후 0은 수명주기 표시값이며 새 CUDA API 측정값이 아니다. HAMi의 종료 Worker 행은 있을 수 있으므로 실행 이름·Pod UID·PID로 원본과 연결해 읽는다.

재조회 예시(독립 디렉터리와 빈 scrape 설정 사용):

```bash
mkdir replay
tar -xJf prometheus-tsdb.tar.xz -C replay
cat > replay/prometheus.yml <<'YAML'
global:
  scrape_interval: 1s
scrape_configs: []
YAML
prometheus --config.file=replay/prometheus.yml \
  --storage.tsdb.path=replay/prom-data \
  --storage.tsdb.retention.time=10y \
  --web.listen-address=127.0.0.1:19096
```

장기간 후 재조회 시 retention을 충분히 길게 지정해 과거 표본이 삭제되지 않도록 한다.
Grafana datasource UID는 `vram-prom`, Prometheus URL은 `http://127.0.0.1:19096`으로 설정한다.
`dashboard.json`을 import하고 각 캡처의 `capture.json`에 있는 절대 from/to 시각과 run 필터를 사용한다.
그림에서 점 사이 연결선은 Grafana의 표시 방식이며 누락 데이터를 별도 생성한 것이 아니다.
