# 3단계 재현과 원본 확인

## 오프라인 검증

저장소 루트에서 Python 표준 라이브러리만으로 실행한다. Kubernetes·CUDA·Grafana는 필요하지 않다.

```sh
for pair in 1 2 3; do
  python3 experiments/evidence/verify_stage3.py \
    experiments/evidence/results/2026-09-29-stage3/pair-$pair
done
```

검증기는 원본 stdout/stderr, 호스트 수신 기록, UID·GPU·한도, 실제 압축 출력 표본을 읽는다. 기준 출력은 각 VM의 seed와 실제 완료 횟수로 재생성한다. 자체 작성한 PASS JSON만 읽어 성공을 판정하지 않는다.

## 실제 GPU 재실행 전제

이 실험은 기존 gpu-4 Kubernetes/KubeVirt/HAMi 환경과 두 개의 Released backing PVC를 재사용했다. [2단계 선행 환경](../2026-09-28-stage2/REPRODUCE.md) 및 protocol.json·identity.json의 이미지 digest를 확인한다.

- `flyt-evidence` namespace, `evidence-vm-a-backing`, `evidence-pair-b-backing` PVC. 이전 연결이 Released여야 한다.
- 기존 UID별 CPU·라이브러리 관측 helper `evidence-c28-affinity`.
- `.local/evidence-20260924/images.json`의 control/hook 이미지와 고정 Guest 이미지.
- 비공개 artifacts에 Guest SSH 키와 공개키, 동일 `libflyt_guest.so`, `stage3-probe` 바이너리.
- 공통 준비 코드 호환용 campaign-probe-guest/native도 artifacts에 필요하나 이 실험에서는 실행하지 않는다.
- GPU UUID의 현재 사용 상태, Worker 이미지의 노드 캐시 가용 여부를 먼저 확인한다. 기존 VM·다른 GPU 작업을 중단하지 않는다.

프로그램 빌드 명령은 build.json에 있다. build 이미지는 기존 Stage2 CUDA 12.8.1 devel 환경을 재사용한다. Guest 라이브러리와 Worker를 새로 빌드했다면 별도 버전 묶음으로 보고한다.

## 수집과 실행

실제 사용한 수집 시작 스크립트는 [sources/start-monitor.py](sources/start-monitor.py), 계측 설정은 [monitoring](monitoring/)에 있다. 이 스크립트의 기본 대시보드보다 **공개된 최종 dashboard JSON이 화면 재현의 기준**이다. 최종 구성에는 실제 사건 목록 패널과 범례의 최대값을 추가했다.

시작 스크립트는 Prometheus/Grafana 기존 바이너리를 사용한다. 새 실행에서는 base/output 경로와 VM 이름을 새 값으로 변경한다. 인증 정보는 비공개 작업 경로에 생성하며 공개하지 않는다. 사용 포트는 localhost 9898(지표), 9098(Prometheus), 3301(Grafana)다.

```sh
python3 experiments/evidence/run_stage3.py \
  --base .local/stage3-20260929 \
  --output experiments/evidence/results/2026-09-29-stage3
```

위 명령은 **이번 실제 실행 명령**이다. 이미 존재하는 결과 경로는 거절한다. 재실행하려면 비공개 artifacts 경로·새 결과 경로와 runner의 VM 이름 접두사를 먼저 바꾼다. 기존 원본을 지우고 재사용하지 않는다.

프로그램은 동일 SSH 연결의 stdin으로 `large → small(A만) → free → exit` 명령을 받는다. B는 큰 할당을 유지하는 동안 약 1초 간격으로 GPU 계산·동기화·표본 검산을 반복한다. 300초 alarm과 UID별 drain으로 실패 시에도 실험 자원을 정리한다. 준비·실패·회수 로그를 보존한다.

## 시계열과 정적 화면

```sh
python3 experiments/evidence/export_stage3.py \
  --base .local/stage3-20260929 \
  --output experiments/evidence/results/2026-09-29-stage3
```

export는 실제 Prometheus의 query_range 결과를 저장하고 Grafana에 실제 사건 annotation을 추가한다. 재실행하면 annotation이 중복될 수 있으므로 새 Grafana 데이터 디렉터리에서 한 번 수행한다. [Prometheus API](https://prometheus.io/docs/prometheus/latest/querying/api/)와 [Grafana annotation API](https://grafana.com/docs/grafana/latest/developer-resources/api-reference/http-api/api-legacy/annotations/)를 사용한다.

스크린샷 도구는 `scripts/capture-stage3-static.cjs`, `scripts/capture-stage3-grafana.cjs`다. Playwright·tmux·jq·Python 및 비공개 base의 표준 ttyd 실행 파일이 필요하다.

```sh
NODE_PATH="$PWD/.local/evidence-20260924/tools/node_modules" \
node scripts/capture-stage3-static.cjs \
  experiments/evidence/results/2026-09-29-stage3 .local/stage3-20260929

NODE_PATH="$PWD/.local/evidence-20260924/tools/node_modules" \
node scripts/capture-stage3-grafana.cjs \
  experiments/evidence/results/2026-09-29-stage3
```

PNG만 저장한다. 명령·화면 텍스트·UTC·URL을 함께 보존하며, 기존 결과에 재실행해 캡처 시각과 파일을 덮어쓰지 않는다. 캡처를 다시 만들 때는 별도 결과 복사본을 사용한다.

수집 프로세스는 비공개 monitor-processes.json의 PID와 명령을 대조해 종료했다. 실험이 끝난 후 이미지 유지 Pod와 점검 Pod도 삭제했다. 인증 파일·SSH 키·전체 cloud-init은 공개 묶음에 포함하지 않는다.
