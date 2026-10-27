# 경로 최적화 코드 준비 기록

후속 실제 VM 실험(2026-10-27): PCI BAR 통합·자식 장애 복구·VM 세대 전환 검증과
Flyt/control/candidate 각 5개 VM 성능 비교를 완료했다. control 대비 실행시간 34.3% 감소,
Flyt 대비 종합 10.0% 증가로 승격 조건 미충족. 운영·main·릴리스 이미지·Helm 변경 없음.
[결과와 검증 한계](../results/20261027-path-optimization-vm/REPORT.md),
[다음 개선안](../results/20261027-path-optimization-vm/NEXT-STEPS.md). 아래 준비/검증 전 표기는 과거 기록이다.

2026-10-27 KST. 상태: **CODE_PREPARED / 빌드·테스트·실험 미실행**.

후속 상태: 사용자의 검증 요청에 따라 별도 후보에서 빌드·회귀·sanitizer·호스트 SHM/GPU
정확성 검사를 수행하고 두 문제를 수정했다. [검증 결과](../results/20261027-path-optimization-validation/README.md).
아래는 검증 실행 전 준비 시점의 기록이다.

[전체 수정 계획](20261027-path-optimization.md)에 따라 별도 후보 소스에서 P1~P7a의 구현과 후속 검증 자료를 준비했다. 원본 제품 파일과 기존 native memset 후보는 변경하지 않았다.

후보 위치: `/home/ubuntu/taeuk/vmweave-path-optimization-20261027`.

- [준비 내역](../results/20261027-path-optimization-validation/archive/README.md)
- [상태](../results/20261027-path-optimization-validation/archive/status.json)
- [소유권·프로토콜 계약](../results/20261027-path-optimization-validation/archive/docs/OWNERSHIP.md)
- [후속 검증 인계](../results/20261027-path-optimization-validation/archive/docs/VALIDATION-HANDOFF.md)

구현 내용: Guest→bulk 직접 복사, Broker scratch 재사용, Worker caller-owned snapshot, 분리 입력 SHM 전송, host 부모/자식 payload arena, native transport owner, host eventfd 알림, bounded pinned/event pool. 모든 신규 기능은 기본 OFF다. 단계별 patch와 후보 파일 hash를 함께 보존했다.

P5는 기존 Python socket protocol을 보존하면서 native C owner를 같은 처리 스레드에서 호출하도록 구현했다. Python Broker 전체를 C로 교체한 것은 아니다. P4는 Worker private snapshot을 유지한다. P7b 다중 요청 pipeline·D2H 조기 반환·VM 간 interrupt 배선은 전체 계획에서 제외한 후속 범위로 남긴다.

Python AST·shell syntax·C 텍스트 구분자·순차 patch 재적용 결과를 확인했다. C 컴파일·링크·테스트·sanitizer·GPU 정확성·성능·배포는 수행하지 않았다. 정적 확인은 빌드 성공이나 동작 보장의 근거가 아니다. 실제 C mock와 CPU 테스트는 작성됐으며 추가 실패·동시성 검증 항목은 인계 문서에 명시했다.

이 기록은 로컬 후보 패키지 인덱스다. 원격 저장소 게시·main 반영·실험 완료를 의미하지 않는다.
