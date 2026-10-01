# 재현과 오프라인 검증

## GPU 없는 환경에서 증거 확인

현재 저장소의 원본 로그·출력으로 평가 실험 2를 검증할 수 있습니다.

```sh
python3 experiments/evidence/verify_stage2.py \
  experiments/evidence/results/2026-09-28-stage2-static/raw
(cd experiments/evidence/results/2026-09-28-stage2-static && sha256sum -c SHA256SUMS)
```

이는 보존된 증거의 검증이며 현재 하드웨어에서 새로 GPU 실험을 실행하는 작업은 아닙니다.
다른 평가의 검사 방법은 각 보고서의 재현·검증 절차를 따릅니다.

## 새 성능 실험의 증거 검증

[성능 실행 코드](../../experiments/performance/README.md)와 결과 묶음의 프로토콜을 함께 확인합니다.
오프라인 검증은 원본 체크섬을 먼저 확인하고 `verify.py`로 표본 수·검산 성공 기록·시각·정상 회수를 대조합니다.
`analyze.py`, `plot.py`, `report.py`는 파생 결과를 다시 생성합니다. 실행 검증 PASS와 이용률 상한 준수는 별도 판정입니다.
분석은 Python 3.12, NumPy 2.5.3, Matplotlib 3.9.4를 사용했습니다.

완료된 결과 묶음은 다음 순서로 확인합니다. 재분석은 복사본에서 수행하면
공개된 원본과 체크섬을 그대로 유지할 수 있습니다.

```sh
(cd experiments/evidence/results/2026-09-30-performance && sha256sum -c SHA256SUMS)
cp -a experiments/evidence/results/2026-09-30-performance /tmp/vmweave-performance-review
python3 experiments/performance/verify.py /tmp/vmweave-performance-review
python3 experiments/performance/analyze.py /tmp/vmweave-performance-review
python3 experiments/performance/plot.py /tmp/vmweave-performance-review
python3 experiments/performance/report.py /tmp/vmweave-performance-review
```

검증 결과의 `campaign_complete`와 `repeat_coverage`를 함께 확인합니다.
중단된 시도는 `interruptions.json`과 원래 실행 디렉터리에 남아 있으며,
새 이름의 대체 실행만 완료 반복에 포함합니다. 자원 정리·모니터링 보존은
측정 검증과 별개로 `final-audit.json`에서 확인합니다.

새 GPU 측정에는 기록된 이미지·키·프로토콜과 새로운 출력 경로를 준비해야 합니다.
실행 도구는 기록된 testbed용이며 다른 클러스터의 자동 설치 도구가 아닙니다.

## 현재 VMWeave에서 새 GPU 실행

[신규 실험 가이드](new-experiments.md)를 따릅니다. 새 API 호환이 확인된 실행기부터 사용합니다.

## 과거 구현의 실험 재현

아래는 당시 커밋·이미지·구 API를 전제로 한 역사 재현 문서입니다.
현재 클러스터의 설치 지침으로 사용하지 않습니다. 과거 재현은 별도 환경에서 수행합니다.

- [VM SHM 실행](../../experiments/evidence/REPRODUCE_VM_DEVELOPMENT.md)
- [고정 PyTorch 학습](../../experiments/evidence/REPRODUCE_PYTORCH.md)
- [실험 2 재현](../../experiments/evidence/results/2026-09-28-stage2/REPRODUCE.md)
- [오버헤드 비교 재현](../../experiments/evidence/results/2026-09-29-overhead/REPRODUCE.md)

원본 보고서는 해당 실행 커밋과 이미지 기준입니다. 현재 `main`에서 경로가 이동한 소스는
[이동 기록](../development/repository.md)을 참고하거나 기록된 커밋을 별도 checkout합니다.

## 기록할 항목

코드 SHA·미커밋 diff 여부, 이미지 digest, GPU/CPU 배치, 도구 버전, 입력·seed,
워밍업·반복 수·측정 경계, raw 출력, 성공·실패·제외 판정, 정상 회수 증거를 함께 저장합니다.
재실행은 새 디렉터리에서 수행합니다. 체크섬이 있는 기존 결과를 덮어쓰지 않습니다.
