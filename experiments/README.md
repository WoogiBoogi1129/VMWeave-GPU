# 실험 실행과 증거

현재 [실험·평가 문서](../docs/evaluation/index.md)에서 목적별 결과를 찾을 수 있습니다.

- `h2d-diagnosis/`: 16MiB H2D의 재현·단계 계측·Guest 복사 제거 대조 실험.
- `evidence/`: 실행·수집·분석·검증 도구 및 날짜별 결과 묶음.
- 그 외 디렉터리: SHM 전환 당시 단계별 계약·검증 계획 기록.
- 현재 빌드에서 사용하는 계약·큐·CUDA dispatcher는 `runtime/shm/`로 이동했습니다.

기존 결과의 내부 경로·해시·성공/실패 내역을 보존합니다.
새 재실행은 새 결과 디렉터리를 사용합니다.

- [2026-10-12~13 VRAM 할당량 및 성능 경합 결과](thesis-isolation/report.md)
- [2026-10-16~17 VMWeave와 passthrough VM의 동일 FP32 학습 성능 비교](ai-passthrough/README.md)
- [2026-10-28 VM 내부 2노드 Kubernetes·GPU Pod 결과·캡처 및 향후 중앙 Operator 실습](nested-k8s-gpu/README.md)
