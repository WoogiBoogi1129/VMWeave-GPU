# 채널 수명 주기

## 준비와 실행

1. 승인 GPUProfile과 정지된 VM, 해당 UID를 참조하는 GPURequest를 준비합니다.
2. 같은 노드의 로컬 PVC와 Worker·hook·control 이미지 digest를 고정합니다.
3. Channel이 backing을 준비하고 `BackingReady`를 기록합니다.
4. VM 시작 후 Guest에 layout을 전달하고 ivshmem BDF·slot을 지정합니다.
5. Guest/Worker mapping ACK와 Ready를 확인한 뒤 지원 CUDA 작업을 실행합니다.

이 순서는 자동으로 VM을 시작하거나 전체 Guest 환경을 설치해 준다는 의미가 아닙니다.
실험 도구가 환경별 준비를 수행하는 범위는 각 재현 문서에 기록합니다.

## 종료와 회수

종료 요청 후 진행 중 작업을 drain하고 Guest·Worker의 해제 증거를 확인합니다.
실행 세대와 attachment 식별자가 맞는지 확인한 뒤 backing과 Worker 자원을 회수합니다.
최종 `Released`, 관련 Worker/VMI 상태와 backing 점검 결과를 증거로 보존합니다.

원격 삭제나 강제 종료 뒤 증거가 부족하면 finalizer가 남을 수 있습니다.
파일 삭제나 finalizer 강제 제거를 정상 회수의 대체 절차로 사용하지 않습니다.

## 관측의 경계

`allocation + generation + session_id + request_id`로 요청의 네 지점을 연결합니다.
Guest와 Worker의 monotonic clock은 독립적이므로 두 시각을 빼 단방향 지연을 계산하지 않습니다.
추적 옵션은 기능 확인에 사용하고 성능 측정 조건과 구분합니다.

[API·추적 옵션](../reference/api.md) · [운영 점검](../guides/operations.md)
