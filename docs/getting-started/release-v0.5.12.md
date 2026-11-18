# VMWeave v0.5.12: 선택적 커널 제출 배치 처리

Guest·Worker에 등록된 typed `cuLaunchKernel`의 default-stream 제출을 묶는 기능을 추가한다.
**기본값은 비활성화**이며 Broker 클라이언트에서 `VMWEAVE_KERNEL_BATCH=1`로 선택한다.
공용 워크로드에 일괄 활성화하지 않는다. Operator chart는 0.5.12,
같은 Guest 라이브러리를 배포하는 Device Plugin 패키지는 0.1.4다.

## 동작과 제한

- 최대 128개 launch를 한 요청으로 전송하며 인자 내용을 즉시 복사한다.
- 큐가 가득 차거나 다른 원격 CUDA 작업/동기화에 도달하면 순서를 보존하며 전송한다.
- 별도 스레드의 200µs flush 목표는 진행 보장 수단이며 최대 지연 보장은 아니다.
- Worker는 전체 패킷을 검증한 뒤 순서대로 실행한다. 실패한 부분 실행은 재전송하지 않는다.
- 오류가 나중의 launch/sync에서 관측될 수 있으며 실패 세션은 다시 연결해야 한다.
- 명시적으로 미지원인 이전 Worker는 동기 경로로 동작한다. 프로토콜 오류는 성공으로 숨기지 않는다.
- 다중 stream, CUDA Graph, 임의 PyTorch 모델에 대한 성능·호환성 보장은 아니다.

상세 계약과 재현용 테스트는
[배치 실험 명세](../../tests/integration/KERNEL_BATCH_EXPERIMENT.md)를 따른다.
발행 전 GPU1 실험은 동일 후보 바이너리의 off/on을 5쌍으로 비교했다.
K=1000 처리량 평균은 1,980 → 72,583 kernels/s였으며,
K=1 비용비의 95% 구간은 0.971–1.063으로 5% 비열등성 판정은 불확정이었다.
이 수치는 발행 전 후보의 결과이며 새 공개 이미지의 성능 측정으로 표시하지 않는다.

## 업그레이드와 롤백

기존 namespace·TLS·mode·GPU 예산을 유지하며 Operator image와 chart를 함께 갱신한다.
CRD, SHM ring ABI 및 기존 API 지원 범위는 바꾸지 않는다.
Helm upgrade만으로 Guest 파일과 기존 immutable Worker Profile이 바뀌지 않는다.
활성 GPU 소비자가 없음을 확인하고 Guest 패키지를 백업한 뒤 VM을 정상 정지한다.
Channel 회수 및 VMI 제거를 확인한 후 새 digest의 Profile/Request/Channel로 재생성한다.
Guest library와 Plugin의 `librarySHA256`을 함께 갱신하며 기존 슬롯 수를 유지한다.
이전 Profile/Request와 패키지는 롤백용으로 보존한다.
사용 중인 다른 VM이나 증거 없이 Draining인 Channel은 강제로 재생성하지 않는다.

롤백도 GPU 소비자가 없는 상태에서 동일한 정상 회수 절차를 거쳐
이전 Guest·Worker·Plugin digest와 hash를 복원한다. 옵션만 끄면 새 바이너리의
기존 동기 경로를 사용할 수 있다. HAMi/DRA/KubeVirt 등 공용 인프라 업그레이드는 필요하지 않다.

게시된 digest와 실제 배포 검증은 [릴리스 목록](../releases/index.md)의 기록으로 확인한다.
