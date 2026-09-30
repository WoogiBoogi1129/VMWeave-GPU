# 실험과 평가

실험은 주장과 원본 증거를 연결해 읽습니다. 아래의 **평가 실험 1~3**은
개발 브랜치의 Stage 1~7과 다른 분류입니다.

| 평가 | 관측 결과 | 원본·재현 |
|---|---|---|
| 1. 요청과 실행 연결 | 요청 등록→배치→GPU 실행→검산→회수 기록 | [실제 터미널 기록](../../experiments/evidence/results/2026-09-28-stage1-terminal/README.md) |
| 2. SHM 요청 왕복 | 새 대표 실행 1회, 18요청·72추적 레코드, 정수 262,144개 불일치 0 | [정적 화면과 원본](../../experiments/evidence/results/2026-09-28-stage2-static/README.md) |
| 3. 두 VM 메모리 제한 | VM 쌍 3/3 PASS, 1 GiB/4 GiB 정책과 OOM 후 재할당 | [평가 요약](memory.md) |
| N/T/S 오버헤드 | 경로별 3회, 유효 63구간; 현재 S 지연이 T보다 큼 | [평가 요약](overhead.md) |
| 연산 상한·공유 성능 | 9/30 새 campaign 실행 중; 예비 상한 25 위반 관측 | [새 평가](resource-performance.md) |
| 제한된 PyTorch 학습 | 고정 FP32 eager MLP·SGD, passthrough와 정확성 비교 | [구현·검증 보고서](../../experiments/evidence/PYTORCH_IMPLEMENTATION_2026-09-22.md) |

## 재현과 판정

[재현 절차](reproduction.md)는 오프라인 증거 검증과 GPU 재실행을 구분합니다.
실행 성공만으로 전체 실험 계획을 PASS로 바꾸지 않습니다.
실패·제외·대체·중단 기록은 해당 결과의 일부입니다.

과거 2026-09-28 실험 2의 독립 실행 3회와 9월 29일 종료된 대표 재실행 1회는
서로 다른 자료입니다. 최신 화면을 과거 실행의 촬영본처럼 설명하지 않습니다.
터미널/Grafana 정적 캡처는 수집된 로그와 시계열을 사후 조회한 화면입니다.

[전체 증거 색인](catalog.md) · [보존·인용 정책](artifacts.md)
