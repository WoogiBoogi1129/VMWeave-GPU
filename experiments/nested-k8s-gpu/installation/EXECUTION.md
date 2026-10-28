# 실행 환경 확정 및 계획 보완

- 실행: 2026-10-28, 증거: `../results/20261028-minimal/`.
- 새 workload namespace: `vmweave-nested-k8s`. 기존 VM/Channel/서비스는 변경하지 않는다.
- 기존 Operator의 관리 대상에 이 namespace가 없으므로, 동일 배포 digest의 별도 Operator를
  `vmweave-nested-system`에 설치한다. admission selector/RBAC는 새 namespace에만 연결한다.
  기존 CRD는 그대로 사용하며 설치 도구의 CRD 재적용 단계는 실행하지 않는다.
- 외부 노드 gpu-4, GPU UUID `GPU-7d708c42-8d4a-16d5-0746-474567157aa3`.
  Worker VM용 승인 quota 50% / 2048 MiB. 기존 같은 GPU 예약은 50% / 2048 MiB이고
  사전 조회 시 GPU 메모리 사용량은 0 MiB였다. GPU 3의 기존 작업은 보호한다.
- OS: 보관된 Ubuntu 22.04 qcow2 원본에서 별도의 sparse raw 디스크 40/80 GiB로 변환.
  기존 실행 중 디스크는 사용하지 않는다. local PV는 gpu-4에 고정하고 Retain을 적용한다.
- Multus 공통망이 없어 Guest 전용 WireGuard를 구성한다. CP `10.245.0.10`, Worker
  `10.245.0.11`, UDP 51820, MTU 1220. 각 VM을 선택하는 외부 ClusterIP Service를 peer
  endpoint로 사용하므로 VMI Pod IP 변경에 의존하지 않는다. 서비스/라우트 범위는 새 VM이다.
- 내부 Pod CIDR `10.246.0.0/16`, Service CIDR `10.247.0.0/16`.
  외부 Pod `10.85.0.0/16`, Service `10.96.0.0/12` 및 조회한 호스트 라우트와 중복하지 않는다.
- Cilium VXLAN, 기준 MTU 1220 / 노드 간 route MTU 1170, IPAM kubernetes, kube-proxy 유지. kubelet은 wg0의 IP를 명시하고
  부팅 시 wg-quick 이후 시작한다. CP API endpoint/SAN은 `10.245.0.10:6443`이다.
- 설치기 commit `25b80e29bf2de6ec2363f052ea26e5c56210eb03`의 단계별 실행을 사용한다.
  원본/수정 hash 및 patch를 보존한다. Kubernetes 1.35.9-1.1, CRI-O 1.35.10-1.1,
  Cilium 1.20.2. Helm/Cilium CLI는 로컬 검증 도구를 복사하고 hash를 고정한다.
- Guest/Worker/helper/hook은 현재 배포된 v0.5.5 digest와 일치하도록 고정한다.
  경로 최적화 후보는 사용하지 않는다.
- WireGuard rollback: 새 Guest wg-quick 중지 및 설정 제거, 새 VM용 Service 제거.
  Operator 철거는 새 Channel 회수 후 별도 Helm release만 uninstall한다.
- 자격증명은 git 밖 `.local/nested-k8s-20261028/` 및 Guest의 권한 제한 파일에 보관한다.
  공개 증거에 private key/join token/kubeconfig를 포함하지 않는다.

위 내용은 현재 환경에 맞춘 실행 명세다. 단계별 실제 성공 여부는 결과 보고서에서 판정한다.

실행 중 설치기 보정: CP init 대기 루프의 `i`를 함수 local 변수로 선언했다.
CRI-O 저장소는 addons URL의 403 때문에 OpenSUSE로 통일했다. 새 Guest의 기본 bridge CNI
설정은 백업 후 비활성화하고 Cilium 단독 구성을 사용한다. 초기 배포의 Cilium readiness는
이미지 다운로드 때문에 기본 5분을 초과해 기존 배포에 대한 확인만 연장한다.

Cilium 재기동 시 API Service 주소를 통한 초기 접속 timeout을 관측하여
`k8sServiceHost=10.245.0.10`, `k8sServicePort=6443`을 명시했다.
Guest 기본 NIC MTU는 1280이다. WireGuard 1220 및 Cilium 기준 MTU 1220에서
노드 간 VXLAN route MTU는 1170이며, 해당 크기의 ICMP와 양방향 통신을 확인했다.
VXLAN은 [Cilium 공식 routing 설명](https://docs.cilium.io/en/stable/network/concepts/routing/)의
50바이트 오버헤드를 반영했다. 최초 설정·실패 및 수정 후 증거는 분리 보존한다.
