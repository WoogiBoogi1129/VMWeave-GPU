# 재현 및 복구

환경 전용 canary 실행기다. 기존 운영 VM을 변경하지 않는다. 유휴 GPU UUID,
VM 이미지·키·fixture·CUDA bundle과 release digest를 확인한 뒤 실행한다.
기존 결과를 덮어쓰지 않으며 같은 canary 이름이 남아 있으면 먼저 UID를 확인한다.

## 빌드와 오프라인 검증

이번 빌드 이미지는 로컬 `6438dfe90905` (CUDA 12.8.1/cuDNN development)이다.

```sh
mkdir -p .local/math-cache-20261022
podman run --rm -v "$PWD:/repo" -w /repo 6438dfe90905 sh -ec \
  'cmake -S runtime/shm -B .local/math-cache-20261022/build -DCMAKE_BUILD_TYPE=Release && cmake --build .local/math-cache-20261022/build --target vmweave_guest --parallel 4'
# CMake가 만든 legacy symlink를 먼저 제거해야 기준 파일 복사 시 후보를 덮어쓰지 않는다.
rm .local/math-cache-20261022/build/libflyt_guest.so
cp .local/naming-release-20261022/published-guest/libvmweave_guest.so .local/math-cache-20261022/build/libflyt_guest.so
cp .local/ai-passthrough-20261021/{small,medium,large}.pt .local/math-cache-20261022/
cc -shared -fPIC -O2 experiments/ai-passthrough/results/20261022-math-cache/client_profile.c -o .local/math-cache-20261022/client-profile.so -ldl -pthread
VMWEAVE_TEST_GUEST_LIBRARY="$PWD/.local/math-cache-20261022/build/libvmweave_guest.so" python3 tests/control/test_math_cache.py
VMWEAVE_TEST_GUEST_LIBRARY="$PWD/.local/math-cache-20261022/build/libvmweave_guest.so" python3 tests/control/test_state_cache.py
make test-control
make docs-check
```

## GPU 검증

`run.py`는 새 VM `ai-math-cache-1022`, profile과 임시 admin Pod를 사용한다.
기준은 공개 v0.5.1 Guest/Worker이고 후보는 변경된 Guest ELF다. Helper와 Hook은
기존 실행기의 호환 이미지를 사용한다. HAMi 라이브러리는 변경하지 않는다.
세 fixture를 준비하지만 학습 검증은 small/batch1024/resident/FP32 하나다.
실제 math mode 설정/조회 검증은 학습 workload를 추가하는 것이 아닌 API 의미 검사다.

이번 실행에서는 별도 터미널에서 `fault_watch.py`를 먼저 시작하고 `run.py`를
실행했다. fault coordinator는 고정 canary 이름과 실제 Worker Pod UID를 확인한 뒤
해당 Pod의 `--session` child 하나만 종료한다. 다른 Pod는 대상으로 삼지 않는다.

```sh
python3 experiments/ai-passthrough/results/20261022-math-cache/fault_watch.py
# 별도 터미널:
python3 experiments/ai-passthrough/results/20261022-math-cache/run.py
# 두 실행이 종료되고 자원 회수가 완료된 뒤, broker 장애의 새 transport 복구:
python3 experiments/ai-passthrough/results/20261022-math-cache/recovery.py
# 분석:
.local/evidence-venv/bin/python experiments/ai-passthrough/results/20261022-math-cache/analyze.py
```

성능 3블록은 계측기를 끈 기준→후보→복원이다. 별도 profile 두 번에만 계측기를
사용한다. 후보의 math cache hit 증가량 1,000, miss 증가량 0을 분석기가 검증한다.
GPU 의미 검사는 실제 mode 0/2, 다중 handle, 변경·중복·오류·동시 호출,
Worker child 종료 뒤 cached setter 오류, 새 프로세스 복구, broker 종료 뒤 오류를 확인한다.

## 비활성화와 회수

`VMWEAVE_BLAS_MATH_CACHE`를 unset 또는 `0`으로 설정하고 애플리케이션을 새로
시작하면 기존 전달 동작으로 복귀한다. 설정은 연결 시 한 번 읽는다.
세션 장애 뒤 같은 프로세스의 자동 재연결은 지원하지 않는다.
Worker child 장애 뒤 broker가 CLOSE를 완료하면 새 프로세스로 새 세션을 연다.
broker 자체의 강제 종료는 SHM transport 소유자도 잃으므로 단순한 캐시 초기화로
복구하지 않는다. 채널/VM 수명주기 절차에 따라 transport를 새로 구성해야 한다.

`run.py`의 finally가 canary VM, 채널, PVC/PV, GPURequest/Profile, admin Pod를
회수한다. 비정상 종료 시 같은 이름과 기록된 UID를 확인하고 기존 drain/reclaim
절차를 따른다. 운영 변경은 없으므로 운영 이미지 롤백은 필요하지 않다.

원시 데이터와 텐서/ELF: `.local/math-cache-20261022/`.
배포·main 반영·이미지 및 Helm 공개는 이 실행기의 범위에 포함하지 않는다.

`recovery.py`는 별도 `ai-math-recovery-1022` 채널/VM으로 transport를 새로 만들고
동일 Guest ELF의 실제 GPU API 의미 검사를 두 새 프로세스에서 반복한다.
처리량 측정은 하지 않으며 장애 주입도 하지 않는다. 기존 broker의 in-place 재시작이나
자동 복구를 검증한 것으로 해석하지 않는다. 종료 시 해당 복구용 자원도 회수한다.
