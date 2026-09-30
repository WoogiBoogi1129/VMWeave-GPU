# 지원·검증 현황

**제어기 검증: 2026-09-30. 새 성능 측정: 2026-09-30 시작, 10월 1일 계속.**
N/T/S 및 연산 상한은 새 Go Operator에서 측정했습니다. 기존 학습·메모리 실험은 별도 역사 기록입니다.
[9월 30일 환경 정리](../history/cleanup-2026-09-30.md) 이후 기존 실험 namespace는 삭제했습니다.
소스의 기능 존재, CPU 회귀 통과, 실제 GPU 실행은 서로 다른 검증 수준입니다.

| 항목 | 확인된 범위 | 근거 |
|---|---|---|
| 중앙 Go Operator | 새 API·두 namespace 검증 | [현재 검증 범위](../development/operator-validation.md) |
| 구 Python review 제어기 | 과거 CPU 클러스터 검증 기록 | [과거 검증 보고서](../../legacy/docs/CONTROL_PLANE_VALIDATION.md) |
| VM SHM GPU 실행 | 실제 VM에서 복사·PTX 실행·정상 회수 | [구현 검증](../../experiments/evidence/IMPLEMENTATION_AND_VALIDATION_2026-09-22.md) |
| PyTorch 학습 | 고정 빌드의 FP32 eager MLP·SGD | [학습 보고서](../../experiments/evidence/PYTORCH_IMPLEMENTATION_2026-09-22.md) |
| 요청·실행 연결 | 요청·배치·실행·회수 증거 | [실험 1](../evaluation/index.md) |
| SHM 요청 왕복 | 정수 262,144개 불일치 0, 대표 재실행 1회 | [실험 2 원본](../../experiments/evidence/results/2026-09-28-stage2-static/README.md) |
| 두 VM 메모리 한도 | 독립 VM 쌍 3회, OOM 후 동일 세션 재할당 | [실험 3](../evaluation/memory.md) |
| N/T/S 오버헤드 | 경로별 5회·105구간, 8개 지연 지표 모두 S > T | [새 성능 평가](../evaluation/resource-performance.md) |
| 단일 VM 연산 상한 | 20회 완료; 25·50·75는 각 5/5회 사전 상한 기준 위반 | [단일 VM 원본](../../experiments/evidence/results/2026-09-30-performance/SINGLE.md) |

## 지원하지 않거나 검증이 남은 범위

- 임의 PyTorch 프로그램 및 전체 CUDA API 호환성.
- 전체 CUDA Graph 연산/capture, cuBLASLt·cuDNN 전체 연산, NCCL/DDP 및 다중 장치.
- 관측된 연산 이용률 상한 위반의 원인 규명 및 수정 검증. 상한은 처리량 비율 보장이 아님.
- 장애·재시작·강제 종료 전체 행렬, 투명 세션 복원, HA 운영.
- 다른 워크로드·GPU로의 확대 및 전송 방식만의 효과를 분리하는 실험.

이전 단계 문서의 `NOT_RUN`은 그 단계 작성 시점의 기록입니다.
현재 현황은 이 페이지와 연결된 후속 증거를 사용합니다.
[API 상세](../reference/api.md) · [남은 개발](../development/roadmap.md)
