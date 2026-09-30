# Guest 이미지와 디스크 준비

VMWeave Operator 이미지는 VM의 OS 이미지가 아닙니다. 다음 세 가지를 구분합니다.

| 산출물 | 역할 |
|---|---|
| Guest OS containerDisk | KubeVirt가 부팅하는 QCOW2 디스크가 포함된 이미지 |
| Guest artifact | `libflyt_guest.so`와 실행할 CUDA 프로그램 |
| Worker/helper/hook image | 사용자 namespace에서 GPU 실행·backing·domain XML 처리를 수행 |

`images/vmweave/Runtime.Containerfile`의 `guest-artifacts` target은 라이브러리 묶음입니다.
부팅 가능한 OS containerDisk로 사용할 수 없습니다. 공개 배포된 완성 Guest 이미지는 현재 제공하지 않습니다.

## OS 디스크

Ubuntu 22.04 계열 등 Guest artifact와 호환되는 OS의 **오프라인 QCOW2 복사본**을 준비합니다.
OS 공급자의 고정 버전 이미지와 체크섬, 준비에 사용한 명령을 기록합니다.
root 디스크 크기, cloud-init의 root 확장, SSH server·Python 3·sudo 설치 여부를 확인합니다.

```sh
mkdir -p .local/guest-disk
# 준비한 오프라인 OS 디스크를 .local/guest-disk/disk.qcow2에 둡니다.
qemu-img info .local/guest-disk/disk.qcow2
qemu-img check .local/guest-disk/disk.qcow2
sha256sum .local/guest-disk/disk.qcow2
docker build -f images/vmweave/GuestDisk.Containerfile \
  -t YOUR_REGISTRY/vmweave-guest:VERSION .local/guest-disk
docker push YOUR_REGISTRY/vmweave-guest:VERSION
```

외부 backing 파일에 의존하는 QCOW2는 먼저 `qemu-img convert -O qcow2`로 독립된 **다른 출력 파일**을 만듭니다.
실행 중 VM 디스크를 이 준비 절차로 수정하지 않습니다. push 결과 digest를 사용자 VM 예제에 입력합니다.

자동 smoke는 `ubuntu` SSH 계정, 해당 계정의 passwordless sudo, Python 3와
실행 호스트에서 Guest Pod IP로의 SSH 접근을 전제로 합니다. 사용자 VM의
`spec.template.spec`에 다음 디스크와 volume을 기존 root 항목에 추가합니다.

```yaml
domain:
  devices:
    disks:
    - name: cloudinit
      disk: {bus: virtio}
volumes:
- name: cloudinit
  cloudInitNoCloud:
    userData: |
      #cloud-config
      users:
      - name: ubuntu
        shell: /bin/bash
        sudo: ALL=(ALL) NOPASSWD:ALL
        ssh_authorized_keys:
        - YOUR_SSH_PUBLIC_KEY
      ssh_pwauth: false
```

이 YAML은 추가할 필드 예시입니다. 기존 CPU·메모리·root disk·network 설정을 덮어쓰지 않습니다.
SSH 비밀키는 로컬에만 보관합니다. 패키지 설치가 필요하면 OS 준비 단계에서 미리 설치해 반복 부팅 시간을 줄일 수 있습니다.

## smoke 프로그램과 shim

동일 소스·CUDA 헤더로 artifact를 준비합니다. 다음 빌드는 CUDA 개발 image를 사용하며 GPU 실행은 하지 않습니다.

```sh
docker build -f images/vmweave/Runtime.Containerfile --target build -t vmweave-runtime-build:local .
mkdir -p .local/guest-artifacts
docker run --rm -v "$PWD:/repo:ro" -v "$PWD/.local/guest-artifacts:/out" \
  vmweave-runtime-build:local sh -ec '
    cp /opt/flyt/lib/libflyt_guest.so /out/
    gcc -O2 -I/usr/local/cuda/include /repo/experiments/evidence/guest_gpu_smoke.c \
      -L/opt/flyt/lib -Wl,-rpath,\$ORIGIN -lflyt_guest -o /out/guest-gpu-smoke
    gcc -x c -O2 -I/usr/local/cuda/include /repo/experiments/evidence/memory_probe.cu \
      -L/opt/flyt/lib -Wl,-rpath,\$ORIGIN -lflyt_guest -o /out/memory-probe-guest
  '
sha256sum .local/guest-artifacts/*
```

`.local/guest-artifacts`를 smoke의 `--artifacts`로 지정합니다. Guest에서 실행되는 동적 라이브러리 의존성도 확인합니다.
이는 PyTorch wheel·CUDA 사용자 라이브러리 전체를 준비하는 절차가 아닙니다.

## 시작 시간과 데이터 수명

매번 OS 이미지를 빌드하지 않습니다. 이미지 준비/pull·노드 캐시, virt-launcher 준비,
실행별 쓰기 overlay, Guest 부팅/cloud-init, VMWeave prepare·Worker·mapping 시간을 구분해 측정합니다.

| 저장장치 | 용도와 보존 |
|---|---|
| OS containerDisk | VMI 실행의 쓰기 변경분은 종료 후 재생성 시 유지되지 않음 |
| 영구 OS PVC | VM의 root disk를 PVC로 연결해 OS 변경분 보관; 별도 백업 필요 |
| SHM backing PVC | allocation 파일용. OS root와 별개이며 정상 회수 시 allocation 파일 삭제 |

containerDisk를 다시 부팅하면 이미지에 미리 반영하지 않은 설치·설정 작업이 반복될 수 있습니다.
실제 반복 여부는 Guest 초기화 설정에 달려 있습니다. `Retain`은 PVC 삭제 후 PV의 데이터 처리 정책이며 백업을 대신하지 않습니다.
