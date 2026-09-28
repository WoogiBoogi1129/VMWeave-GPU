# 실제 모니터링 기록

이 디렉터리는 이번 실행에서 수집한 Prometheus/Grafana 자료다. 호출 지연의
원본은 각 실행 디렉터리의 CSV/XZ이며, 1초 GPU 이용률에서 추정하지 않는다.

- `*.json`: `export.json`에 명시한 실제 Prometheus query-range 응답.
- `cpu.jsonl.gz`: 서로 겹치지 않는 Pod cgroup의 누적 CPU counter.
- `observations.jsonl.gz`: 실제 NVIDIA GPU 관측값과 수집 상태.
- `overhead.json`, `grafana-dashboard-api.json`: 사용한 dashboard 정의.
- `annotations.json`: 실제 측정 시작·종료 시각과 완료 횟수로 등록한 annotation.
- `prometheus-tsdb.tar.gz`: 수집 서버를 정상 종료한 후 보존한 실제 TSDB.
- `service-cleanup.json`: 해당 실험의 기록된 PID/명령 확인과 종료 기록.

GPU 이용률·메모리·전력·클록은 물리 GPU 전체 기준이다. CPU 합계는 native Pod
또는 VM launcher + GPU server/Worker Pod이며, 공용 controller·manager/Mongo·
모니터링의 CPU는 포함하지 않는다. 작업 처리율은 30/60초 측정 구간별 값이며,
1초마다 완료 횟수를 수집한 시계열은 없다. Grafana의 annotation은 구간을
표시할 뿐 초별 처리율 측정값을 만들어 내지 않는다.

## 보관 데이터 다시 열기

새 디렉터리에 압축을 풀고 원래 버전인 Prometheus 3.5.0으로 연다.
아래 `prometheus`는 해당 버전 실행 파일의 경로로 바꾼다.

```sh
mkdir restored-overhead
cd restored-overhead
tar -xzf /path/to/prometheus-tsdb.tar.gz
printf 'global:\n  scrape_interval: 1s\nscrape_configs: []\n' > read-only.yml
prometheus --config.file=read-only.yml --storage.tsdb.path=prom-data \
  --storage.tsdb.retention.time=3650d --web.listen-address=127.0.0.1:9098
```

보관 원본의 복사본을 사용한다. 재조회 서버에는 scrape 대상을 지정하지 않는다.
Grafana 12.0.2에서 Prometheus datasource UID를 `perf-prom`, URL을 위 서버로
설정하고 `overhead.json`을 가져온다. 컨테이너를 사용한다면 URL은 해당 컨테이너에서
접근 가능한 주소로 바꾼다. `../grafana-captures/metadata.json`의 `from`/`to`는
밀리초 단위 절대 UTC 시각이며, 이 구간을 선택해야 과거 측정값이 보인다.

Grafana의 별도 DB와 관리자 비밀번호는 배포하지 않는다. Annotation을 복구할
때는 `annotations.json` 각 항목의 `request`를 새 서버의 `/api/annotations`에
등록한다. 새 서버의 인증값을 사용하며 실험 서버 인증값을 재사용하지 않는다.
