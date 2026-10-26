# 시험 패치 빌드와 재검증

이 문서는 기존 패키지를 수정하지 않는 독립 복사본 빌드 절차다. 기준 소스 commit, 복구 전 수정, 변경 파일 및 결과 바이너리 해시는 `manifest.json`과 `patches/`에 있다. 기준 빌드·서버 이미지는 `build-environment.json`의 content ID로 식별한다. 공개된 분석 산출물 재생성에는 이 GPU 빌드가 필요하지 않다.

1. `https://github.com/sam990/flyt.git`의 guest/host 기준 commit을 **서로 다른 새 디렉터리**에 checkout한다. 기록된 `*-preexisting.patch`가 비어 있지 않으면 먼저 적용한다. 기존 사용 중인 Flyt 또는 VMWeave checkout에 적용하지 않는다.
2. 해당 디렉터리에서 `git apply --check <guest 또는 host.patch>` 후 적용한다. 기존 Rodinia 빌드의 CUDA 12.8.1, GCC 11, libtirpc 설치본, CUDA/cuBLAS/cuDNN/NVML 개발 의존성이 필요하다. 사전 빌드된 submodule/라이브러리와 컨트롤 매니저는 기록된 기준 빌드의 보관본을 사용했다. 이들 대형 바이너리는 이번 저장소 산출물에 포함하지 않았다.
3. 기록된 `localhost/flyt-threeway-build:20261025-full` 이미지의 새 소스 마운트에서 빌드한다. 기존 소스는 쓰기 마운트하지 않는다.

```sh
# guest 독립 복사본의 cpu/ 안에서
make -j4 cricket-client.so TARGET_LIBCUDART_MAJOR_VERS=12 LOG=ERROR
# host 독립 복사본의 cpu/ 안에서
make -j4 cricket-rpc-server TARGET_LIBCUDART_MAJOR_VERS=12 LOG=ERROR
```

`resource-map.h`의 레이아웃이 바뀌므로 이전 오브젝트를 재사용할 때 `resource-map.h` 또는 `cpu-server-client-mgr.h`를 직접·간접 포함하는 서버 번역 단위를 재컴파일해야 한다. 새 checkout에서는 모두 새로 빌드한다. 이번 실행은 분리한 복사본에서 영향받는 오브젝트를 제거한 뒤 재빌드했다. 기존 Makefile의 링크 옵션·의존성은 유지했으므로 일반적인 모든 API의 링크/런타임 지원을 보장하는 패키지가 아니다.

단위 검증 예시(경로는 새 checkout과 이 증거 디렉터리에 맞춘다):

```sh
gcc -Wall -Wextra -Werror -fsanitize=address,undefined -g \
  -I"$FLYT_HOST_COPY/cpu" tests/test-ranges.c \
  "$FLYT_HOST_COPY/cpu/resource-map.c" -lpthread -o /tmp/flyt-test-ranges
/tmp/flyt-test-ranges

gcc -I/usr/local/cuda/include -rdynamic tests/test-entrypoint.c \
  "$FLYT_GUEST_COPY/cpu/cpu-client-entrypoint.c" -ldl -o /tmp/flyt-test-entrypoint
/tmp/flyt-test-entrypoint
```

범위 검사는 내부/끝 경계/해제/재사용/다른 클라이언트/일반 핸들/구조체 내부 주소 보존을 확인한다. API 검사는 실제 포인터 호출, 반환 상태·소유 모듈 검사 경로, 미지원 flags·버전·그래프와 capture/launch 전달을 다룬다. CUDA 관련 최소 프로그램과 `qualify.py`는 실행 당시 전용 시험 VM의 SSH 설정 및 로컬 경로를 전제로 하므로 다른 환경에서 경로·자원을 지정한 뒤 사용해야 한다. 자격증명은 제공하지 않는다.

실제 검증은 별도 namespace, 새 VM, 별도 4GiB SHM backing/VM, 공유 시험용 MPS pipe, VM별 서버, 94 SM 및 2GiB 조건에서 수행했다. VM의 시험 디렉터리 `/tmp/flyt-test/`에서만 라이브러리 링크를 만들었고 고정 절대 경로가 필요한 기준 번들은 새 VM 내부 `/opt/torch-venv`에 풀었다. 기준 번들 원본은 변경하지 않았다. 최종 시험 패키지는 새 `.local/flyt-compatibility-20261026/packages/` 아래에 보관하며 기존 태그·패키지를 대체하지 않는다.

본실험은 진단용 `CUDA_LAUNCH_BLOCKING`과 커널/cuBLAS 추적 로그를 제거한 최종 빌드를 사용했다. 본실험 소스·실행 규칙은 별도 성능 증거 디렉터리에서 확인한다.
