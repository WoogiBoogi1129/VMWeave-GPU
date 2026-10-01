# 남은 개발과 평가

## 구현

- [Go Operator 전환 검증](operator-validation.md)의 미완료 항목: HA 장애 행렬, Node fencing, Go helper 후속 이전.
- CUDA Graph·라이브러리 연산·비동기 의미의 지원 범위 확대.
- Guest 환경 배포와 장치 매핑 자동화 개선.
- 중앙화·새 API 배포와 기존 실험 namespace 정리는 완료. 구 CRD 정의 제거와
  PyTorch campaign의 새 API 전환·재검증은 후속 작업이다. 성능 실행기는 새 API로 전환했다.
- Worker 대기·큐·복사·동기화 비용의 원인 분석과 최적화.
- 이미 Released인 채널의 Foreground 삭제에서도 분리 증거 GC와 최종 처리가 충돌하지 않도록
  제어기 종료 경로 개선. [실제 정리 실패·복구](../../experiments/evidence/results/2026-09-30-performance/cleanup-recovery/README.md)를 회귀 사례로 사용한다.

## 검증

- [새 성능 실험](../evaluation/resource-performance.md)에서 관측한 이용률 상한 위반의 원인 규명과 수정 검증.
- 전체 장애·재시작·강제 종료·회수 행렬.
- 다른 부하·GPU로의 성능 평가 확대, 전송 매체와 HAMi/MPS·실행기 효과의 분리.
- 지원 환경 조합과 재현 가능한 배포 산출물 정비.

기존 fatbinary 등록과 고정 학습 경로는 후속 구현·검증이 있으므로 과거 문서의
미구현 목록을 그대로 현재 TODO로 사용하지 않습니다.
각 변경은 [현재 상태](../overview/status.md)의 근거와 새 실험을 연결해 갱신합니다.
