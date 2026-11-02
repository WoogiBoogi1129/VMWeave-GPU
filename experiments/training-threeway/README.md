# PyTorch Training의 통신·연산 통합 성능 비교

비교군: GPU Passthrough VM, Flyt SHM, 최적화된 VMWeave v0.5.5.
이 디렉터리는 2026-11-02에 시작한 신규 실험의 소스와 결과를 보존한다.
2026-11-03 KST에 정식 300회, 정확성 비교 25건, 변경 입력 전송 검산 24건과 최종 복구를 완료했다.
[최종 보고서와 그래프](results/20261102/REPORT.md)에서 수치·측정 범위·중단 및 복구 기록을 확인한다.
이번 MLP 10조건의 VMWeave 처리량은 Flyt의 2.34–4.24배, Passthrough의 6.9–8.8%였다.

## 평가 범위

동일 eager FP32 MLP 학습에서 작은/큰 모델 × batch32/1024 × GPU 입력 상주/매 step H2D의
8조건과, batch1024 출력 D2H 회수 2조건을 비교한다. 통신과 연산의 전체 완료 시간을 재며,
입력 상주 결과도 CUDA 호출 전달·동기화를 포함한다. 순수 PCIe 대역폭이나 순수 kernel
성능을 나타내지 않는다. 합성 입력 반복이며 모델 정확도/수렴 시간에 대한 일반화는 하지 않는다.

- [사전 계획](results/20261102/PLAN.md)
- [공통 학습 코드](bench.py): 초기화와 워밍업 제외, 16 step별 완료 동기화, final sync 포함.
- [정확성 비교](compare.py): 1/10 step의 전체 출력·weight·gradient와 loss 대조.
- [예비·정식 실행기](campaign.py): 예비 자료로 공통 작업량을 고정하고 정식 10블록 수행.
- [분석기](analyze.py): CPU-only 오프라인 재분석, 대응 블록 기준 기하평균/CI.
- [전송 검증](transfer_check.py): 입력 값을 바꾸는 H2D → GPU 연산 → D2H 보조 검산.
- [증거 검증기](validate.py): 완료 후 실행 수·소스·GPU 할당·복구 기록을 오프라인 확인.
- [호스트 상태 수집](collect_context.py): 기존 Prometheus 이력을 읽는 사이트 전용 도구. GPU 부하를 생성하지 않으며 오프라인 분석과 분리한다.

## 오프라인 재분석

정식 측정이 모두 완료되고 `protocol.json`과 `formal/`이 존재할 때:

```sh
python3 experiments/training-threeway/analyze.py
python3 -m unittest discover -s experiments/training-threeway -p 'test_*.py' -v
python3 experiments/training-threeway/validate.py
```

그림 생성에는 matplotlib가 필요하다. 이번 환경은 `.local/evidence-venv/bin/python`을 사용한다.

```sh
python3 experiments/training-threeway/analyze.py --plots
```

분석은 파생 `measurements.csv`, `summary.json`, `resource-summary.json`, `external-summary.json`과 선택한 그림을 덮어쓴다.
`report.py`는 성능 측정·보조 전송 검증·설정 복구가 완료된 경우에만 최종 보고서를 생성한다.
원본 보존이 필요하면 결과 복사본에 `--root`를 지정한다.

## 실제 GPU 재실행 전제

인프라 도구는 해당 연구 장비용이다. 일반 클러스터에 그대로 실행하지 않는다.
새 실행에는 namespace, VM/PV/PVC, host directory, 결과 경로 및 실행 ID를 바꿔야 한다.
기존 출력은 exclusive-create 방식으로 보호한다.

필요한 외부 아티팩트의 SHA256은 `results/20261102/artifacts.json`에 기록한다.
공통 Guest 디스크, 드라이버 소스/펌웨어, 수정 PyTorch/CUDA bundle, SSH 키,
Flyt 호환 바이너리, 공개 VMWeave Guest package와 컨테이너 이미지는 별도 준비가 필요하다.
키와 runtime database 비밀번호는 Git에 포함하지 않는다. 이 아티팩트 없이 clean clone에서
실제 GPU 실행이 가능하다고 주장하지 않는다. 보존된 JSON/CSV의 분석은 이러한 의존성 없이 가능하다.

Flyt는 [기존 호환 복구](../thesis-isolation/evidence/20261026-flyt-compatibility/manifest.json)의
동일 바이너리를 사용한다. 해당 디렉터리에 기반 commit과 host/guest patch를 보존했다.
VMWeave는 [v0.5.5 이미지](../../deploy/releases/v0.5.5.json)와 일치하는 Guest를 사용한다.

`lab.py`/`prepare.py`는 공통 OS와 시험용 디스크를 준비하고, `backends.py`는 각 실행 경로의
시작/종료를 담당한다. `transition.py`는 GPU0만 VFIO/NVIDIA로 전환한다.
이때 모니터의 장치 FD 해제를 위한 재시작이 필요하므로 운영자 승인 범위를 확인해야 한다.
이번 실행에서는 사용자가 GPU0 임시 포함·모니터 재시작·원래 설정 복구를 명시적으로 승인했다.
원래 설정은 `.local/`에 보존하며 최종 복원 검증 결과만 결과 디렉터리에 공개한다.

정확성 전체 tensor blob은 큰 로컬 아티팩트로 보존하고 Git에는 hash와 전체 tensor별
비교 지표를 담는다. 한 번의 실행 내부 step이나 센서 표본은 독립 실험 반복으로 세지 않는다.

## 중단 블록 복구

9번째 블록의 Passthrough 기동 중 PCIe 연결 단절·복귀가 관측돼 해당 기동이 실패했다.
`resume_after_pci_event.py`는 복구 probe 통과를 확인한 뒤 중단 블록의 Flyt 10회를 별도 보존하고,
확정 protocol을 바꾸지 않고 9번째 블록 전체와 남은 10번째 블록을 수행한다.
이 도구는 당시 상태를 전제로 한 일회성 복구 기록이며 재실행용 일반 진입점이 아니다.
정식 300회, 중단 블록 10회, 별도 복구 검산은 보고서에서 구분한다.

전체 파일 무결성은 이 디렉터리에서 `sha256sum -c --quiet SHA256SUMS`로 확인한다.
[오프라인 재분석 검증](results/20261102/offline-reanalysis.json)은 원자료 복사본으로 CSV와
성능·자원·외부 상태 요약을 다시 생성해 파일 해시 일치까지 확인한 기록이다.
[최종 소스 목록](results/20261102/source-manifest.json)은 사전 protocol seal과 구분한다.

정식 완료 후 두 번째 PCIe 사건과 재시도 실행기의 기존 이력 디렉터리 처리 오류가 있었다.
중간 복구 후 검산 VM만 같은 아티팩트로 재구성해 24건을 완료했다. `check_transfers.py`의
`--reuse-host-context`는 원래 성능 측정 기간과 일치하는 기존 이력을 검증 후 재사용한다.
일회성 재구성 실행기와 실패 로그는 결과의 `infrastructure/`에 보존한다.
