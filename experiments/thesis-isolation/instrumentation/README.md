# E2 자기 버퍼 예비 시험 계측

범위는 VM·Worker·CUDA 컨텍스트 대응 확인, 요청 단계 추적, 자기 버퍼 정상 읽기·쓰기다. 교차 접근과 잔존 데이터 검사는 실행하지 않는다.

- `own_boundary.c`: 자기 할당 4 KiB 두 개만 사용한다. 읽기 대상과 출력 버퍼를 분리하고 출력 첫 워드를 sentinel로 초기화한다. 외부 주소를 입력받지 않는다. 쓰기는 자기 버퍼 첫 4바이트만 변경하며 전체 4 KiB를 검증한다.
- `context_observer.c`: `cuLaunchKernel`의 인자를 변경하지 않고 다음 구현에 전달한다. 현재 컨텍스트와 반환 코드를 기록한다. 기존 HAMi preload는 유지한다. 컨텍스트 핸들 값은 프로세스 내부 값이므로 서로 다른 프로세스의 숫자만 비교하지 않는다.
- `worker-wrapper.sh`: 위 관측기를 해당 시험 Worker 프로세스에 로드한다.
- `Worker.Containerfile`: 현재 `runtime/shm` 소스로 재빌드한 Worker와 기존 런타임 환경을 조합한다. 기존 캠페인 바이너리와 동일하다고 주장하지 않는다.
- `normalize_oci.py`: 기존 이미지의 history 개수 불일치만 보정한다. 모든 파일시스템 레이어는 원본 바이트를 보존한다. 원본 이미지 태그는 변경하지 않는다.

초기 실행에서는 기존 Worker 바이너리를 그대로 사용했으나 해당 바이너리에 `FLYT_TRACE`가 없음을 확인했다. 또한 호스트 정보 수집의 `kubectl exec -i` 누락을 수정했다. 해당 준비 실패와 회수 기록은 삭제하지 않는다.

재현 입력은 각 캠페인의 `build.json`에 원본/시험 이미지 digest, Worker/관측기 해시, 현재 런타임 소스 해시로 기록한다. 빌드는 CUDA 12.8 도구가 있는 기존 `localhost/flyt-build:stage2-20260928` 이미지에서 CMake Release로 수행한다. 관측기와 probe는 기존 `localhost/vmweave-e2-env:20261012`의 gcc로 빌드하며 네트워크는 사용하지 않는다. `Worker.Containerfile` 빌드 컨텍스트에는 `install/bin/flyt-shm-worker`, `context-observer.so`, `worker-wrapper.sh`가 필요하다.

실행 도구는 `runner/own_boundary_pilot.py`, 독립적인 사후 요청 연결 검증은 `runner/analyze_own_boundary.py <캠페인 경로>`다. 새 시험마다 고유 실행 ID를 생성한다. `ISOLATION_HELPER`로 실행 중인 관리자 helper를 지정하며, `boundary-build/image.json`의 시험 이미지와 전용 GPUProfile을 사용한다. 프로파일은 immutable이므로 다른 이미지 실험에는 새 프로파일 이름이 필요하다.

Guest submit/receive와 Worker take/respond는 allocation, generation, session_id, request_id로 연결한다. Worker take/respond 사이의 컨텍스트 기록을 해당 launch에 연결한다. 서로 다른 머신의 monotonic timestamp를 직접 빼서 지연시간으로 해석하지 않는다. 커널 제출 성공만으로 실행 성공을 판단하지 않고 동기화와 데이터 검증 결과를 함께 확인한다.

보호 경계의 교차 접근 차단 여부는 이 시험의 판정 대상이 아니다. 소스에 IPC 메모리 공유 dispatch가 없고 본 probe가 공유 API를 호출하지 않는다는 점은 기록하되, 시스템 전체의 모든 공유 경로를 감사한 것으로 확대하지 않는다.

## 별도 Native CUDA 대조군 준비

`probes/native_boundary.c`와 `runner/native_boundary_prepare.py`는 제품 Worker를 실행하지 않는 별도 CUDA/HAMi 대조군이다. 전용 Pod 두 개에 원본 런타임 이미지, 동일 시험 GPU, 메모리 2048 MiB, GPU core 설정 50을 적용한다. 직접 연결한 CUDA runtime/driver API로 자기 할당만 읽고 쓴다. 시험 바이너리만 읽기 전용으로 마운트하며 Guest 키·설정은 마운트하지 않는다.

프로그램은 GPU UUID·단일 가시 GPU·HAMi 라이브러리 로딩·Guest shim 미로딩·가시 메모리 할당량을 확인한다. `cuCtxGetCurrent`, `cuMemGetAddressRange`로 현재 컨텍스트와 자기 할당 주소 범위를 기록한다. 컨텍스트 값은 프로세스 내부 핸들이므로 호스트 PID와 함께 식별한다. 상대 주소는 실행기가 같은 시점에 유지 중인 짝 프로세스의 ready 기록에서만 가져온다. 준비 단계의 `mapping` 명령은 주소 범위 메타데이터 조회이며 GPU 메모리 load/store를 발행하지 않는다. 커널 명령은 자기 버퍼 `read`/`write`만 구현했다.

컴파일은 기존 `localhost/vmweave-e2-env:20261012`에서 gcc `-Wall -Wextra -Werror`, CUDA include/lib64 및 driver stub 링크 디렉터리, `-lcudart -lcuda`로 수행한다. 실행 산출물은 `.local/thesis-isolation-20261012/artifacts/native-boundary`이다. 실행 시 driver stub가 아닌 실제 NVIDIA 드라이버 로딩을 프로세스 maps로 기록한다.

`runner/analyze_native_prepare.py <캠페인 경로>`는 GPU를 실행하지 않고 원시 기록을 다시 검사한다. 이 대조군 결과는 VMWeave 제품 경로의 종단 간 검증으로 해석하지 않는다.

다음 GPU 접근 예비 시험에서는 새 프로세스 쌍과 새 합성 버퍼를 사용해야 한다. 이전 실행의 주소는 회수 후 무효다. 지정 버퍼 생존·소유 관계와 정상 대조군을 확인한 뒤 양방향 읽기·쓰기를 각각 별도 프로세스 쌍에서 시험한다. 자기 할당 alias나 불명확한 대상 매핑은 별도 분류하며, API 사전 거절·커널 제출·동기화 오류·상대 버퍼 검증을 구분한다. 치명적 CUDA 오류가 난 프로세스는 재사용하지 않는다. 본 준비 실행에서는 이 GPU 교차 접근 단계를 수행하지 않았다.

## Native 교차 접근 예비 실행 도구

`probes/native_peer.c`는 준비용 소스와 별도로 유지한다. 실행기가 유지 중인 짝 프로세스의 ready 기록에서 받은 단일 주소에 대해 4바이트 읽기 또는 쓰기를 한 번 실행한다. 자기 버퍼 alias나 주소 조회 결과가 예상 조건과 다른 경우 커널을 발행하지 않는다. 커널 인자는 직접 CUDA Driver API에 전달되며 Guest shim·제품 Worker는 사용하지 않는다. IPC 공유나 임의 주소 탐색은 없다.

`runner/native_peer_pilot.py <ab|ba> <read|write>`는 한 조건만 실행한다. `runner/native_peer_campaign.py`는 새 프로세스 쌍으로 4개 조건을 순차 실행하고 예상 밖 결과나 회수 실패 시 후속 조건을 중단한다. `runner/analyze_native_peer.py <캠페인 경로>`는 제출·동기화·소유 관계·상대의 후속 실행·회수를 독립 검증한다. 실행 중 CUDA 오류가 난 요청 프로세스의 종료 코드 1은 조건에서 예상한 상태이며, 캠페인 성공 여부는 관측 및 정상 회수를 함께 확인해 결정한다. GPU 리셋이나 보호 설정 변경은 수행하지 않는다.
