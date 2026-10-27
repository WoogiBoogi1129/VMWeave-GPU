# VMWeave 경로 최적화 후보 검증

후속 실제 VM 실험과 Flyt 5회 비교를 수행했다. [최신 보고서](../20261027-path-optimization-vm/REPORT.md).
control 대비 34.3% 개선했지만 Flyt 대비 종합 10.0% 느려 운영 승격은 하지 않았다. 아래는 선행 검증 기록이다.

2026-10-27 KST. [전체 코드 수정 계획](../../plans/20261027-path-optimization.md)의
별도 후보에 대해 빌드·회귀 검사·CPU sanitizer·실제 GPU를 이용한 호스트 SHM 경로
정확성 검증을 수행했다.

- 전체 빌드 및 CPU/CUDA mock/기존 회귀 검사 통과. layout 권한 검사에서 root 전용 2개는 제외.
- GPU 기본값·단일 기능·누적 적용 19조건 통과. last-error 수정 영향 10조건 재검증 통과.
- IPC 잘못된 메시지·알림·타임아웃 검사, 세션 재연결·FD 정리·자식 사망 후 복구 통과.
- 응답 `transport_status` 초기화와 native memset의 이전 오류 유지 처리 두 곳 수정.

[상세 결과와 로그](archive/validation/REPORT.md),
[최종 상태](archive/status.json),
[수정 패치](archive/patches/P10-validation-fixes.patch).

실제 제품 경로를 사용하되 Broker의 PCI BAR mapping만 테스트용 파일 mapping으로
대체했다. 따라서 실제 VM/ivshmem 통합과 Flyt 대비 성능 개선의 검증 결과는 아니다.
운영 코드·배포는 변경하지 않았으며 신규 옵션은 기본 OFF다. 다음 단계는 실제 VM
통합 검증과 독립 반복 성능 비교다.
