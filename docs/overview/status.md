# 지원·검증 현황

**현황 색인 갱신: 2026-11-13.** 현재 배포 버전은 [릴리스 색인](../releases/index.md)을 따릅니다.
검증은 아래처럼 버전·실행별로 구분합니다. 일부 조건 성공을 전체 호환성·운영 안정성으로 확대하지 않습니다.

| 후속 검증 | 확인 범위 | 근거 |
|---|---|---|
| 11/13 legacy CNN 후보 | Conv2d forward/backward, 두 Conv 블록·ReLU·MaxPool·Linear·SGD, MNIST 일부 기능 검사. 기본 graph·BatchNorm·AMP 제외 | [작은 CNN](../../experiments/cnn-model/README.md), [backward](../../experiments/cnn-training/README.md) |
| 11/8 v0.5.9·Device Plugin v0.1.1 | 기본 cuDNN LSTM·cuBLASLt 학습, 공개 이미지로 128 step·CPU 검산·체크포인트 재개, 노드 업데이트 | [검증](../../deploy/releases/evidence/v0.5.9/README.md) |
| 11/5 Device Plugin v0.1.0 | 실제 VM 내부 K8s GPU 예약·주입, 단일 client, SIGKILL/재시작/브로커 장애·VM 재기동, 공개 패키지 실행 | [검증](../development/device-plugin-validation-2026-11-05.md) |
| 11/4 v0.5.8 회수 기록 | API/filesystem 중단 복구, CRD/RBAC, 배포 상태. 물리 GPU detach·새 VM 부팅 시험은 아님 | [릴리스](../getting-started/release-v0.5.8.md) |
| 11/2~3 학습 비교 | VMWeave v0.5.5·Flyt·Passthrough의 제한된 합성 MLP, 정식 300회 | [보고서](../../experiments/training-threeway/results/20261102/REPORT.md) |
| 10/28~30 내부 Kubernetes | 비특권 GPU Pod, Guest/Pod SGEMM·복사·Rodinia. 내부 Device Plugin 미사용 | [실험 색인](../../experiments/nested-k8s-gpu/README.md) |
| 10/16 VRAM 계상 | 할당 경계·동시 조건·물리 메모리 관측 | [보고서](../../experiments/vram-accounting/README.md) |

아래 표는 **9/30 제어기와 9/30~10/1 성능 실험 등 기존 증거**다. 각 수치는 당시 빌드와 조건에 한정한다.
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
| 다중 VM 부하 시작·종료 | 20쌍 완료; 처리량 유지율 약 49.4–50.1%, 상한 25는 공유 중에도 기준 위반 | [통합 결과·중단 이력](../../experiments/evidence/results/2026-09-30-performance/README.md) |

## 지원하지 않거나 검증이 남은 범위

- 임의 PyTorch 프로그램 및 전체 CUDA API 호환성.
- 전체 CUDA Graph 연산/capture, cuBLASLt·cuDNN 전체 연산, NCCL/DDP 및 다중 장치.
- 과거 상한 위반 기록은 해당 빌드의 결과이며, 후속 검증은 [증거 색인](../evaluation/catalog.md)에서 구분한다. 모든 부하·GPU에 대한 상한 및 처리량 비율 보장은 하지 않는다.
- 장애·재시작·강제 종료 전체 행렬, 투명 세션 복원, HA 운영.
- 다른 워크로드·GPU로의 확대 및 전송 방식만의 효과를 분리하는 실험.

이전 단계 문서의 `NOT_RUN`은 그 단계 작성 시점의 기록입니다.
현재 현황은 이 페이지와 연결된 후속 증거를 사용합니다.
[API 상세](../reference/api.md) · [남은 개발](../development/roadmap.md)
