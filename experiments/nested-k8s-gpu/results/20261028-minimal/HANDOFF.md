# 검토용 클러스터 접속·재현·복구

새 VM 두 대와 GPU Channel은 유지 중이다. 테스트 부하는 종료됐으며 compute 50% / GPU memory 2048 MiB 예약은 유지된다.
클러스터는 단일 CP·단일 Worker PoC이고, 외부 변경과 함께 관측된 결과의 해석 제한은 [REPORT.md](REPORT.md)에 있다.

## 접속과 상태 조회

다음 명령은 `/home/ubuntu/taeuk/flyt-k8s-poc-github`에서 실행한다.
외부 kube-context와 내부 kubeconfig를 구분한다. SSH 키는 git 밖 `.local/nested-k8s-20261028/id_ed25519`에 있다.

```bash
kubectl --context kubernetes-admin@kubernetes -n vmweave-nested-k8s get vm,vmi,sharedmemorychannel
python3 experiments/nested-k8s-gpu/runner/common.py cp 'sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf get nodes -o wide'
python3 experiments/nested-k8s-gpu/runner/common.py cp 'sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf get jobs,pods -n nested-validation'
```

VM 간 고정 주소는 CP `10.245.0.10`, Worker `10.245.0.11`이다.
호스트에서 SSH할 때 사용하는 외부 ClusterIP Service는 각각 `10.96.178.29:22`, `10.99.41.66:22`다.
runner는 Service 주소를 조회해서 연결한다. VMI Pod IP는 재생성 시 바뀌므로 고정 접속 주소로 쓰지 않는다.

`g2-no-socket`, `g4-sigkill`, `g6-active` Job의 실패는 의도한 대조·장애 결과다.
GPU Job의 `status.active`는 모두 0이다. 마지막 정상 결과는 `g6-recovery`다.

## 추가 GPU 작업을 1회 검토할 때

다음은 이번 완료 실험에 이미 포함된 실행이 아니라 사용자가 이후 필요할 때 수행하는 명령이다.
새 이름을 사용한다. runner는 이전 CUDA 자식 회수 확인 → Job 생성 → GPU PID 대응 수집 →
관측 barrier 해제 → 전 원소 비교 → 세션 회수 순서로 실행한다.

```bash
python3 experiments/nested-k8s-gpu/runner/gpu.py review-20261028-01
```

고정 이미지는 `localhost/nested-gpu@sha256:82a988dfa68d030c31a2ca0cac9543a5f655a0d40e151d5b60cb0e3b770a00ff`이며
Worker의 CRI-O 저장소에 있다. registry에 공개 배포한 이미지는 아니다. Worker root PVC가 있어야 보존된다.
직접 Job YAML을 재사용할 경우 `/tmp/run` 관측 barrier 해제가 필요하므로 runner를 사용하는 것이 편하다.
동시에 별도 Guest CUDA 프로그램이나 두 GPU Job을 실행하지 않는다.

## broker/transport 장애의 수동 복구

1. 새 GPU 작업 제출을 중지하고 기존 Pod/Worker 프로세스 증거를 보존한다.
2. 실험 Worker VM만 Halted로 전환하고 VMI 제거와 Channel `Stopped / RuntimeReclaimed`를 확인한다.
3. 같은 VM을 Always로 전환한다. Channel Ready·새 allocation/generation/Worker UID·broker active를 확인한다.
4. 두 Node Ready와 새 boot ID 반영을 확인한 다음 새 이름의 GPU Job 1회로 복구를 검증한다.

```bash
kubectl --context kubernetes-admin@kubernetes -n vmweave-nested-k8s patch vm vw-k8s-worker-01 --type=merge -p '{"spec":{"runStrategy":"Halted"}}'
kubectl --context kubernetes-admin@kubernetes -n vmweave-nested-k8s wait --for=delete vmi/vw-k8s-worker-01 --timeout=180s
kubectl --context kubernetes-admin@kubernetes -n vmweave-nested-k8s wait --for=jsonpath='{.status.phase}'=Stopped sharedmemorychannel/vw-k8s-worker-01 --timeout=180s
kubectl --context kubernetes-admin@kubernetes -n vmweave-nested-k8s patch vm vw-k8s-worker-01 --type=merge -p '{"spec":{"runStrategy":"Always"}}'
kubectl --context kubernetes-admin@kubernetes -n vmweave-nested-k8s wait --for=jsonpath='{.status.phase}'=Ready sharedmemorychannel/vw-k8s-worker-01 --timeout=300s
python3 experiments/nested-k8s-gpu/runner/common.py worker 'sudo systemctl is-active vmweave-guest-broker kubelet crio; cat /proc/sys/kernel/random/boot_id'
python3 experiments/nested-k8s-gpu/runner/common.py cp 'sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf get nodes -o wide'
```

기존 SHM ring에 broker service만 재시작하는 복구는 사용하지 않는다. 전역 GPU reset, 공유 Operator 변경,
기존 운영 VM 변경은 이 절차에 포함하지 않는다. CP VM을 중단하면 내부 Kubernetes API도 중단된다.

## 철거

데이터·etcd·증거 보존 → 새 작업 차단 → CUDA 자식 회수 → Worker Halted 및 Channel Stopped 확인 →
VMWeave 계약에 따른 Channel/Request 회수 → 새 VM·PVC·PV 정리 → 전용 Operator와 namespace 정리 순서다.
local PV는 Retain이므로 API 삭제만으로 파일이 제거되지 않는다. `.local/nested-k8s-20261028/`의
실험 디스크 외에 기존 VM 디스크를 삭제하지 않는다. 이 실험에서는 철거를 실행하지 않았다.
