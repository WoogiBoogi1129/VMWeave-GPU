# 지원·검증 현황

**제어기 검증: 2026-09-30. 성능·학습 측정: 2026-09-29까지.**
기존 성능·학습 수치는 새 Go Operator에서 재측정한 결과가 아닙니다.
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
| N/T/S 오버헤드 | 경로별 3회, 유효 63구간; 확장 반복 미완료 | [오버헤드 평가](../evaluation/overhead.md) |

## 지원하지 않거나 검증이 남은 범위

- 임의 PyTorch 프로그램 및 전체 CUDA API 호환성.
- 전체 CUDA Graph 연산/capture, cuBLASLt·cuDNN 전체 연산, NCCL/DDP 및 다중 장치.
- 연산 설정 25/50/100의 전체 제한 계약과 공정성 판정.
- 장애·재시작·강제 종료 전체 행렬, 투명 세션 복원, HA 운영.
- 전체 계획에 따른 성능 반복과 전송 방식만의 효과를 분리하는 실험.

이전 단계 문서의 `NOT_RUN`은 그 단계 작성 시점의 기록입니다.
현재 현황은 이 페이지와 연결된 후속 증거를 사용합니다.
[API 상세](../reference/api.md) · [남은 개발](../development/roadmap.md)
