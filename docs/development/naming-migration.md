# VMWeave 명칭 전환 (v0.5.1)

현재 실행 코드와 설정의 기본 이름을 `VMWEAVE_*`, `vmweave_*`,
`vmweave-shm-*`, `/opt/vmweave`로 통일합니다. 상태 캐시는
`VMWEAVE_STATE_CACHE=1`로 켜며 기본값은 비활성입니다.

## 호환 규칙

| 경계 | 새 이름 | 기존 이름 처리 |
|---|---|---|
| 환경변수 | `VMWEAVE_*` | 새 변수가 없을 때만 `FLYT_*` fallback; `0`과 빈 문자열도 새 값 우선 |
| C API | `vmweave_*` | 공개 `flyt_*` 심볼은 동일 주소의 ABI alias |
| CUDA 확장 | `vmweaveRegisterKernelABI` | `flytRegisterKernelABI`는 동일 주소의 ABI alias |
| 헤더 | `vmweave_*.h` | `flyt_*.h`는 canonical 헤더와 식별자 매핑을 제공하는 deprecated wrapper |
| 라이브러리 | `libvmweave_guest.so` | `libflyt_guest.so` symlink |
| 실행 파일 | `vmweave-shm-worker`, `vmweave-shm-session-worker` | 기존 실행 파일명 symlink |
| 설치 경로 | `/opt/vmweave` | 패키지의 `/opt/flyt` alias; Guest installer는 기존 디렉터리를 보존한 뒤 전환 |
| CMake | `VMWEAVE_BUILD_CUDA_RUNTIME`, 새 target | 기존 옵션 fallback 및 link target alias, 기존 산출물명 symlink |

공통 C/Python 환경변수 접근 함수가 우선순위를 구현합니다. broker는 자기 자신을
클라이언트로 잘못 연결하지 않도록 두 이름의 broker socket 설정을 모두 제거합니다.
환경변수 namespace를 바꿔도 별도의 캐시나 세션 상태를 만들지 않습니다.
구형 preload 계측기는 내부 호출을 관찰하려면 새 `vmweave_*` 심볼을 대상으로
다시 빌드해야 합니다. 기존 ABI 이름을 제공하는 것과 내부 interposition 경로가
그대로인 것은 서로 다릅니다.

## 의도적으로 유지하는 이름

- `FLYTCHN1`, `FLYTSHM1`: 기존 backing/layout의 wire magic입니다. 숫자 API ID와
  구조체 배치도 유지하므로 이 변경만으로 SHM 프로토콜을 바꾸지 않습니다.
- `flyt.dev` API group, 기존 리소스 plural/finalizer/annotation 처리: 과거 API와
  저장 리소스를 인식하는 호환 코드입니다. 현재 API group은 `vmweave.io`입니다.
- `/flyt-channel`, `/var/run/flyt-channel`: 구형 KubeVirt hook/Worker와 공유하는
  mount 경계입니다. 이번 전환 기간에는 유지하며, 설치 디렉터리와 구분합니다.
- `/tmp/flyt-worker-ready`: 구형 operator의 readiness를 위한 alias입니다.
- 과거 실험 결과, source snapshot, hash manifest, 릴리스 기록과 `legacy/`는
  당시 동작의 증거이므로 수정하지 않습니다.

새 operator는 canonical 실행 경로를 먼저 선택하고 구형 이미지에서는 기존 경로로
실행합니다. Worker 환경변수는 전환 기간에 두 이름을 같은 값으로 전달합니다.
따라서 기존 이미지가 지정된 GPUProfile을 일괄 교체하기 전에도 새 세션을 실행할
수 있습니다. 기존 API의 자동 삭제나 데이터 마이그레이션은 하지 않습니다.

## 검증과 적용

CPU 제어기·배포 테스트, Go race test, CUDA 헤더 기반 회귀, 실제 Guest의 함수 주소
동일성, 두 환경변수의 우선순위, 기존 헤더 컴파일을 검증합니다. 이후 새 패키지의
Guest/Worker로 단일 대표 학습 workload와 장애·재할당을 검증합니다.

운영 업데이트는 최종 `main` commit에서 발행한 이미지 digest와 Helm 버전을
기록한 뒤 수행합니다. Guest broker가 살아 있는 상태에서 파일을 교체하지 않습니다.
VM 중단·세션 회수 후 Guest 설치 파일과 Worker 이미지를 함께 갱신하고 재기동합니다.
기존 버전으로 복구할 때도 기존 설정·이미지·Guest 파일을 복원한 새 세션을 사용합니다.
릴리스 이전의 실험용 이미지 검증과 최종 공개 이미지 검증은 구분해 기록합니다.
