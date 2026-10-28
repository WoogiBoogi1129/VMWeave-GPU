# 설치·실행 중 발견한 문제와 조치

1. CRI-O addons 저장소 Release.key 요청이 HTTP 403. 두 VM을 접근 가능한 OpenSUSE 공식 CRI-O 저장소로 통일했다. 설치 버전은 1.35.10-1.1로 유지했다. 시스템 준비는 재실행하지 않았다.
2. Ubuntu 22.04 Podman 3.4.4는 `build --pull=missing`을 지원하지 않음. 빌드 옵션을 `--pull=false`로 수정했다. 실패는 빌드 시작 전이며 GPU 시험은 실행되지 않았다.
3. CP 설치기의 `step_init_cluster`가 상위 단계 루프의 변수 `i`를 덮어써, 성공한 kubeadm init 후 패키지 설치와 init 단계로 돌아갔다. 두 번째 init은 기존 구성 감지로 중단됐으며 reset은 실행하지 않았다. API /readyz를 독립 확인하고 완료로 기록한 뒤, 실행 복사본에 `local i`를 추가했다. 원본 저장소는 변경하지 않았다.
4. CRI-O/Podman 기본 CNI 설정으로 초기 DNS Pod가 임시 bridge 주소를 받았다. 새 Guest의 기본 설정만 `/root/nested-cni-original`로 옮기고 Cilium만 활성화했다. Cilium 배포 후 DNS Pod 주소·Ready 상태를 확인한다.

5. Cilium 상태 확인의 기본 5분 제한이 이미지 다운로드 중 만료됐다. Helm 설치를 다시 실행하지 않고 기존 배포의 상태 확인만 연장했다. 원본 timeout 로그를 보존한다.

6. K1의 HTTP/DNS/Service 성공 후 ICMP 검사가 `ping: permission denied (are you root?)`로 실패했다. CRI-O 기본 capabilities에 NET_RAW가 없었다. 기존 CPU Pod의 임시 컨테이너에만 NET_RAW를 부여해 실패 조건을 재검증하고, 이후 CPU 검사 manifest 생성에도 해당 권한을 명시했다. GPU Pod의 capability 설정은 변경하지 않았다.

7. NET_RAW 보완 뒤 작은 ICMP는 성공했으나 1280바이트 패킷은 손실됐다. Guest eth0의 실제 MTU가 1280임을 확인했다. WireGuard MTU 1220, Cilium 기준 MTU 1220(노드 간 VXLAN route MTU 1170)으로 수정하고 Cilium 재시작 및 기존 CPU/DNS Pod 네트워크 재생성 후 영향받은 K1 조건을 재검증한다. 첫 K1 결과는 cluster/attempt1에 보존한다.

8. Cilium 재기동 중 Worker init 컨테이너가 API Service(10.247.0.1:443)에 timeout. Cilium API endpoint를 고정 CP 주소(10.245.0.10:6443)로 명시해 정상 복귀했다. 수정 후 K1 전 항목이 PASS했다.

실패 로그와 수정 diff는 raw/, installation/에 보존한다. 이후 GPU 및 복구 시험 실패는 조건별 verification 파일과 원본 로그로 추가 기록한다.
