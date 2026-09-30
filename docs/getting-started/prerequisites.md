# 사전 조건

클러스터 관리자는 다음을 준비합니다.

- Kubernetes API/CRD/RBAC/admission 관리 권한과 Helm 3, Python 3, OpenSSL.
- KubeVirt의 VM/VMI API와 SHM hook을 지원하는 launcher/QEMU 환경.
- GPU 환경에서는 NVIDIA 드라이버·CUDA·HAMi scheduler/device plugin.
- VM과 Worker가 같은 노드에서 접근하는 local filesystem PV/PVC. NFS는 이 backing의 대체재가 아닙니다.
- 호환 Guest/Worker/hook/helper 이미지 digest. `VMWEAVE_API_GROUP=vmweave.io`를 지원하는 Worker helper.
- 이미지 다운로드·압축 해제·백업을 포함한 노드 디스크 여유. `DiskPressure` 및 image GC 임계값을 먼저 확인합니다.
- control-plane과 workload 각각의 registry 접근. 다른 namespace의 imagePullSecret을 참조할 수 없습니다.

새 Go Operator는 Operator SDK v1.42.3으로 scaffold하고 controller-runtime v0.23.3,
Kubernetes client v0.35.0을 사용합니다. 정확한 의존성은 `operator/go.mod`/`go.sum`에 고정합니다.
실험 노드는 Kubernetes v1.37.0·KubeVirt v1.9.0입니다. 이 조합의 실제 시험 범위는
[전환 검증 기록](../development/operator-validation.md)에서 확인합니다.

Go/Operator SDK는 개발자 도구입니다. 배포 이미지를 사용하는 클러스터 관리자는 필요하지 않습니다.
원본 빌드가 필요한 경우 `operator/Makefile`과 `images/vmweave/Operator.Containerfile`을 사용합니다.
기존 CPU review 성공은 CUDA·GPU 실행 검증을 대신하지 않습니다.
