# 소개와 설계 범위

VMWeave-GPU는 KubeVirt VM이 GPU를 직접 PCI 패스스루하지 않고,
같은 노드의 Worker를 통해 GPU 기능을 사용하는 경로를 구현합니다.
VM의 CUDA 호출을 공유 메모리로 전달하고 GPU 요청·할당·회수를 Kubernetes 리소스와 연결합니다.

## 설계 목표

- VM 요청과 실제 Worker·GPU 배치를 식별자로 연결합니다.
- VM과 Worker 사이의 데이터 전달에 SHM request/response ring과 payload 영역을 사용합니다.
- GPU 메모리·연산 자원 설정은 HAMi와 연동합니다.
- 채널 해제는 Guest/Worker의 detach 증거와 실행 세대를 확인합니다.

## Flyt에서 달라진 점

| 영역 | 이전 Flyt 기반 경로 | 현재 기본 경로 |
|---|---|---|
| CUDA 데이터 전달 | Cricket RPC / TCP | VM–Worker SHM 채널 |
| 자원 제어 | Flyt Manager·MPS | Kubernetes 리소스와 HAMi |
| 실행 구성 | Manager·Node Manager·RPC server | Guest·Worker·Channel Controller |
| 소스 위치 | `legacy/rpc/` | `runtime/shm/` |

기존 Flyt/Cricket 개발 계보를 보존합니다. 새 이름은 독립적인 개발 방향을 나타내며,
원본 코드·아이디어의 출처나 기존 라이선스를 대체하지 않습니다.

## 적용 범위

현재 SHM은 동일 노드의 로컬 backing과 VM 장치 매핑을 전제로 합니다.
원격 GPU 네트워크 서비스, 모든 CUDA 프로그램의 투명 실행, 운영 수준의 HA를
제공한다고 주장하지 않습니다. [현재 지원 범위](status.md)를 먼저 확인하세요.
