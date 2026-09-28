# 중단 시점의 실험 시각 자료 목록

> 후속 추가: [2단계 SHM 요청·응답 추적과 계산 정확성](results/2026-09-28-stage2/README.md).
> 독립 실행 3회의 실제 Guest/Worker 로그 화면 19개와 첫 실행 연속 영상 1개를 확보했다.
> 동일 request ID의 1 MiB 할당·복사·커널·동기화·전수 검산·free와 Released를 확인할 수 있다.

> 후속 추가: [1단계 요청–실제 배치·GPU 실행 결과](results/2026-09-28-stage1/README.md).
> 독립 실행 3회의 매핑·검산·회수 화면과 첫 실행 약 131초 영상을 확보했다. 아래 목록은 고정 작업량 중단 직후의 기존 자료 점검 기록이다.

2026-09-28 확인. 고정 작업량 실험은 사용자 결정으로 중단했다. 이 점검에서는 새 GPU 실험을 실행하지 않았다.
실행 중인 `run_campaign.py`, `finish_campaign.py`, `retry_campaign_clock.py` 프로세스는 없었다.
9/28 비공개 실행 원본에는 시간제 18회와 고정 작업량 10회의 완료·회수 기록이 있다.
고정 작업량은 발표용 결과에서 제외한다. C6 오버헤드·공유 간섭 반복 측정은 실행되지 않았다.

GitHub 공개 묶음에는 시간제 18회의 완료 원본, 실제 캡처·영상, 재생성한 그래프와 기존 결과의 보조 그림만 포함한다.
[공개 결과 보고서](results/2026-09-28-campaign/README.md)에서 대표 화면을 바로 볼 수 있다.
고정 작업량 원본과 미완성 캠페인 초안은 로컬에 보존하고 이번 공개에서 제외했다.

## 실제 실행을 보여 주는 자료가 확보된 항목

| 실험 / 날짜 | 화면에서 확인할 수 있는 내용 | 대표 시각 자료 | 활용 판단 |
|---|---|---|---|
| 두 VM의 동일 GPU 동시 사용 / 9/24 | A/B가 Running·Ready, 서로 다른 Worker·allocation, 같은 GPU UUID, 실제 GPU 프로세스 2개 | [실행 화면](results/2026-09-24-showcase/screenshots/two-vm-gpu-sharing.png), [72.52초 실제 화면 영상](results/2026-09-24-showcase/video/two-vm-live.webm) | **가장 명확한 공유 시연 자료.** 두 VM이 동일 GPU를 사용하는 것을 보여 준다. 단독 대비 성능 간섭을 입증하는 자료는 아니다. |
| 1 GiB 메모리 한도·복구 / 9/24 | 설정 1024 MiB, 할당·초과 요청 오류·해제·재할당 출력, 실제 메모리 변화 | [할당](results/2026-09-24-showcase/screenshots/evidence-show-mem-1024-observe-allocated.png), [OOM 후 해제](results/2026-09-24-showcase/screenshots/evidence-show-mem-1024-observe-freed.png), [재할당](results/2026-09-24-showcase/screenshots/evidence-show-mem-1024-observe-reallocated.png), [한도선 포함 그래프](results/2026-09-28-campaign/reused/memory-1024.png) | **발표에 바로 사용 가능.** 동일 세션의 실패 후 복구 범위다. |
| 4 GiB 메모리 한도·복구 / 9/24 | 설정 4096 MiB, `over_quota`의 CUDA 오류 2, `freed` 성공, 재할당 및 계상 복원 | [할당](results/2026-09-24-showcase/screenshots/evidence-show-mem-4096-observe-allocated.png), [OOM 후 해제](results/2026-09-24-showcase/screenshots/evidence-show-mem-4096-observe-freed.png), [재할당](results/2026-09-24-showcase/screenshots/evidence-show-mem-4096-observe-reallocated.png), [한도선 포함 그래프](results/2026-09-28-campaign/reused/memory-4096.png) | **발표에 바로 사용 가능.** OOM 로그는 화면에 있지만 정확한 OOM 발생 시각은 원본에 없다. |
| 정상 종료·자원 회수·재사용 / 9/24 | Released, Worker/VMI 부재, 호스트 GPU 프로세스 부재, 20회 반복 결과 | [호스트에서 확인한 회수 화면](results/2026-09-24-showcase/screenshots/additional-normal-release.png), [20회 결과 그래프](results/2026-09-24-showcase/plots/lifecycle.png), [최종 감사](results/2026-09-24-showcase/final-audit.json) | **발표에 바로 사용 가능.** 한 장의 화면으로 20회를 입증한다고 하지 않고 반복 원본·그래프를 함께 제시한다. |
| 연산 설정별 부하 관측 / 9/24 | 설정 25·50·100의 실제 Worker·GPU 부하, 설정별 3회 관측 | [25 화면](results/2026-09-24-showcase/screenshots/evidence-show-compute-25-1-load.png), [50 화면](results/2026-09-24-showcase/screenshots/evidence-show-compute-50-1-load.png), [100 화면](results/2026-09-24-showcase/screenshots/evidence-show-compute-100-1-load.png), [9회 그래프](results/2026-09-24-showcase/plots/compute-observed.png) | **관측 결과로 사용 가능.** 25/50/100에 비례한 연산 제한을 입증한 결과는 아니다. |
| 긴·짧은 커널의 60초 시간제 측정 / 9/28 | 실제 Grafana 지표, run ID를 포함한 실행 출력, 완료 커널 수·시간, 설정별 처리율 | [Grafana 화면](results/2026-09-28-campaign/captures/compute-100-1/compute-100-1-grafana-end.png), [실제 출력 화면](results/2026-09-28-campaign/captures/compute-100-1/compute-100-1-output.png), [42.08초 Grafana 영상](results/2026-09-28-campaign/captures/compute-100-1/page@9c728d5dd81b508a129c27f9a6c01d83.webm), [18회 처리율 그래프](results/2026-09-28-campaign/figures/c5-time.png), [이용률 시계열](results/2026-09-28-campaign/figures/compute-utilization.png) | **실제 실행 증거와 비교 그래프를 함께 사용.** 아래 화면 한계를 명시한다. |

9/24 화면은 실제 명령 출력을 모은 자체 읽기 전용 대시보드다. Grafana 화면으로 표기하지 않는다.
9/28 화면은 실제 Grafana 및 실제 stdout을 읽는 브라우저 뷰어다. 데스크톱 터미널 직접 녹화와 구분한다.
기존 9/24 결과를 9/28 신규 측정이라고 표시하지 않는다.

### 9/28 시간제 자료의 정확한 범위

- 긴/짧은 커널 × 설정 25/50/100 × 3회 = 18회 완료. 각 실행은 60초이며 마지막 출력 524,288개를 검산했다.
- 대표 live 캡처·영상은 긴 커널 설정 100과 25에서 확보했다. 설정 50의 신규 전용 live 캡처와 모든 반복의 전체 영상은 없다.
- 초기 Grafana 캡처는 `Run ID = All`, 최근 15분 화면이어서 기준 생성·예비 실행도 같이 보인다. 실제 실행 증거로는 쓸 수 있지만, 이 화면만으로 설정별 성능을 비교하면 안 된다.
- 실제 출력 캡처에는 `PROGRESS`와 GPU UUID/PID가 보인다. 이 캡처에는 최종 정확성 `RESULT`가 보이지 않으므로 화면만으로 불일치 0을 증명하지 않는다. 해당 판정은 실행별 결과 JSON으로 확인한다.
- 긴 커널의 첫 설정 25 실행은 guest UTC step으로 GPU 시계열 대응이 불확실하다. 해당 GPU 평균은 제외했고, 단조 시계 기반 처리율은 유효하다. 대체 재실행은 하지 않았다. 나머지 실행은 시계 대응 기록에 따라 분석했다.
- 처리율 그래프는 18회 원본에서 만든 보조 그림이며 live 화면 캡처가 아니다. 새 조건의 연산 제한 판정은 `NOT_EVALUATED`다.

## 결과 그림은 있지만 실행 과정 화면은 부족한 항목

| 항목 | 확보 자료 | 시각 자료로 가능한 주장과 한계 |
|---|---|---|
| PyTorch 계산 정확성 / 9/22 원본 재가공 | [8개 조건·144개 tensor 비교 표](results/2026-09-28-campaign/reused/pytorch-correctness.png), [CSV](results/2026-09-28-campaign/reused/pytorch-correctness.csv) | 결과 정확성 표로 사용 가능. 이번에 학습을 다시 실행한 영상이나 비교 터미널 캡처는 아니다. |
| 두 세션의 4 GiB 합산 제한 / 9/24 원본 재가공 | [합산 요청/성공량 그림](results/2026-09-28-campaign/reused/aggregate.png), [원본 결과](results/2026-09-24-showcase/runs/evidence-show-aggregate/run/metrics.json) | 각 약 2.4 GiB 요청에 `[성공, OOM]`인 결과를 표시한다. 두 세션의 순서를 직접 보여 주는 전용 화면·영상은 없다. 한 세션 해제 후 다른 동일 세션의 재요청 성공은 검증하지 않았다. |

## 이번 확보 목록에서 제외하는 항목

- **고정 작업량 완료시간:** 사용자 요청으로 중단. 10개 완료 기록은 보존하지만 계획한 30회 비교가 끝난 결과로 사용하지 않는다. 이전에 만들어진 `c5-fixed.png`의 파일 존재만으로 완성된 자료라고 판단하지 않는다.
- **native 대 VM 실행 오버헤드:** 예비 실행은 있으나 C6의 조건을 맞춘 반복 비교와 그 시각 자료는 없다.
- **단독 대 동시 실행의 성능 간섭:** C6 비교는 미실행. 기존 두 VM 공유 화면은 동시 사용 증거이며 성능 손실·공정성의 근거가 아니다.
- **환경·조건:** 버전·사양·설정 원본은 있다. 이것을 성능 측정 결과나 실험 성공 화면으로 분류하지 않는다.

## 발표에 사용할 묶음

1. **GPU 공유:** 두 VM live 화면 한 장 + 72초 영상.
2. **메모리 제한과 복구:** 한도별 할당/OOM 후 해제/재할당 화면 + 한도선 포함 그래프.
3. **정상 회수:** 호스트 관측 회수 화면 + 20회 반복 그래프.
4. **연산 부하 특성:** 9/28 실제 Grafana·출력 화면 + 60초 처리율·이용률 그래프. 설정별 비례 제한 성공으로 표현하지 않는다.
5. 정확성 표와 두 세션 합산 그림은 위 자료의 보조 자료로 배치한다.

고정 작업량 완료시간 대신 시간제 실험의 **동일한 60초 동안 완료한 작업 수/처리율**을 사용해도 연산 설정별 관측 결과를 설명할 수 있다.
이는 native 대비 오버헤드나 공유 간섭 비교를 대신하는 것은 아니다.
