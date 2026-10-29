# VM 내부 2노드 Kubernetes·GPU Pod 실습

기존 `vmweave-system` controller/webhook이 관리하는 namespace에 새 VM 두 대를 만들고,
Control Plane과 Worker로 연결하는 [상세 실습 보고서](../../experiments/nested-k8s-gpu/lab/CENTRAL-OPERATOR-LAB.md)를 제공한다.
실습 당일 중앙 배포 이미지와 호환되는 release lock을 확인하며 별도 Operator를 설치하지 않는다.

절차에는 관리 범위·RBAC·admission 사전 점검, 영구 디스크와 새 VM, Kubernetes 설치 스크립트,
WireGuard·Cilium, broker·GPU binding, init/join, CPU/GPU Pod 검증, 원본 캡처와 복구·철거가 포함된다.
내부 Device Plugin 개발과 GPU Extended Resource 선언, 24시간 유지 검증은 포함하지 않는다.

**이 중앙 Operator 경로는 읽기 전용 사전 점검과 오프라인 문서·도구 검증까지 완료했다.**
새 VM 생성부터 GPU 실행까지의 실습은 아직 실행하지 않았다.
[검증 범위](../../experiments/nested-k8s-gpu/lab/VALIDATION.md)를 확인한다.

## 기존 실험 결과와 구분

2026-10-28의 완료된 실험은 별도 `vmweave-nested-system` controller/webhook을 사용했다.
당시 중앙 배포와 이미지 digest는 같지만 중앙 관리 경로로 수행한 실험은 아니다.
두 Node Ready와 GPU Pod 연산·회수 등을 확인했으며, 운영 시험 중 외부 재배포가 겹쳐
환경 불변·장애 영향의 완전한 분리나 장기 안정성을 주장하지 않는다.

- [실험 결과·원본·실습 자료 색인](../../experiments/nested-k8s-gpu/README.md)
- [조건별 결과 보고서](../../experiments/nested-k8s-gpu/results/20261028-minimal/REPORT.md)
- [실제 CP 터미널의 두 Ready 노드 캡처](../../experiments/nested-k8s-gpu/results/20261028-nodes-capture/README.md)
- [유지 자원과 접속·복구 인계](../../experiments/nested-k8s-gpu/results/20261028-minimal/HANDOFF.md)
- [2026-10-29 Guest/Pod SGEMM 처리량 분석](../../experiments/nested-k8s-gpu/results/20261029-sgemm-throughput/REPORT.md)
- [VMWeave·Flyt·Passthrough 기존 결과와의 비교](../../experiments/nested-k8s-gpu/results/20261029-performance-comparison/REPORT.md)
