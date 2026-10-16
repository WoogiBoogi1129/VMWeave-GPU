# 배포용 HAMi Core 제한 수정

2026-10-16 사용자 결정에 따라 `linear-sm + idle-reset`을 배포용으로 승격했다.
50% 설정의 평균 이용률 55.61%는 기존 실험의 ±5%p 기준을 넘지만, 이 수치를
배포 차단 조건에서 제외한다. 기존 측정값이나 합격 기준을 소급 변경하지 않는다.
다중 VM 25/75 비율과 모든 커널의 정확한 상한을 보장한다는 의미는 아니다.

- 기반: HAMi-core `b216ba1be1b8e21488d1c7370ed3357b3049aad1`.
- 적용: SM² 보정 → SM 보정, 토큰 용량 64비트 계산, 유휴 토큰 초기화.
- `patches/0001-sm-limit.patch`는 실험의 `0002` 패치와 동일하다. 실험의
  `0001` 패치를 먼저 적용하면 안 된다.
- [기존 측정 결과](../../experiments/sm-core-limit/limit-validation.md).

## 배포 빌드 검증 (2026-10-16)

`localhost/vmweave-hami:sm-limit-20261016` 빌드 및 실제 이미지 설치 검사를 통과했다.
라이브러리 SHA-256은 `f30f08c8f4bbdada1856231f2ec269d50fc81e08881a4146c9c1bbb3173aebd8`로
기존 9회 VM 검증에 사용한 바이너리와 동일하다. 임시 대상 디렉터리에 설치·재설치하고,
설치 전 열어 둔 파일 descriptor가 이전 내용을 유지하는지 검사했다.

이 빌드의 라이브러리를 추가로 유휴 GPU 2에서 직접 실행했다. 50% 제한,
60초 실행(15초 준비), FORCE 정책, long-kernel 조건에서 정상 종료했고 평균
장치 이용률 54.14%, 52.41 launches/s를 관측했다. 실제 프로세스 매핑도 확인했다.
이는 배포 빌드의 단일 native smoke이며 새로운 VM 반복 실험이나 다중 VM 검증은 아니다.
Core 보정/idle 회귀 검사, Helm 이미지 선택, 저장소 검사 및 문서 검사를 통과했다.
[빌드·검사·GPU 원시 기록](../../experiments/sm-core-limit/evidence/deployment-20261016/)을 보존했다.

현재 단계는 배포 이미지와 릴리스 경로 반영이다. 레지스트리 게시 및 현재 클러스터
업그레이드는 이 검증에서 실행하지 않았다.

## 빌드와 배포

Worker의 `/usr/local/vgpu/libvgpu.so`와 `/etc/ld.so.preload`는 HAMi가
호스트 파일로 마운트한다. 따라서 Worker 이미지에 라이브러리를 복사하는 것으로는
수정본이 적용되지 않는다. HAMi device-plugin 이미지의 배포 자산을 교체해야 한다.

```sh
podman build -f images/hami/Containerfile -t localhost/vmweave-hami:sm-limit .
python3 tests/hami/test_image.py --image localhost/vmweave-hami:sm-limit
```

CI는 main/PR에서 빌드와 설치 검사를 수행하고, 기존 저장소의 릴리스 정책과 같이
`v*` 태그에서 검사에 통과한 `ghcr.io/<owner>/vmweave-hami:<tag>`를 게시한다.
현재 저장소 owner용 [Helm overlay](../../deploy/hami/core-limit-values.yaml)의
`REQUIRED_RELEASE_TAG`를 실제 게시한 태그로 바꾼 뒤 기존 HAMi values에 덧씌운다.
다른 owner로 fork한 경우 repository도 변경한다. 적용 예시:

```sh
helm upgrade hami hami/hami --version 2.10.0 -n kube-system \
  --reuse-values -f deploy/hami/core-limit-values.yaml \
  --set devicePlugin.image.tag="$RELEASE_TAG" --wait
```

기존 HAMi release 이름/namespace/설정에 맞춰 실행한다. 이미지 digest와 배포 전
values를 기록한다. 별도 로컬 레지스트리 사용 시 동일한 이미지 산출물을 게시하고
registry/repository/tag를 지정한다. 이 저장소의 배포 파일 반영만으로 실행 중인
클러스터나 Worker가 자동 업그레이드되지는 않는다.

수정 이미지는 HAMi v2.10.0의 버전별 라이브러리 파일을 제공한다. postStart 설치는
임시 파일을 같은 디렉터리에서 완성하고 rename하여 기존 파일의 inode를 보존한다.
이미 라이브러리를 매핑한 Worker는 이전 코드를 계속 사용한다. 새 Worker에서
`/usr/local/vgpu/libvgpu.so` SHA가 이미지의 `/opt/vmweave/hami/libvgpu.sha256`과
일치하는지 확인하고 GPU smoke를 수행한다. 기존 세션은 정상 종료 후 재생성해야 한다.

롤백도 이전 라이브러리를 임시 파일 + rename으로 복원해야 한다. 실행 중인
Worker가 매핑한 파일에 `cp`로 덮어쓰지 않는다. 이전 upstream 이미지의 설치기는
직접 덮어쓸 수 있으므로 모든 관련 Worker를 정상 종료한 뒤 upstream으로 되돌리거나,
동일한 atomic 설치기를 포함한 롤백 이미지를 사용한다.
