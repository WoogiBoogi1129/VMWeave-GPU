# 빌드와 테스트

## CPU 검증

```sh
make test-control
make check-layout
python3 -m unittest discover -s experiments/evidence/tests -v
helm lint charts/flyt-control-plane \
  --set image.digest=sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  --set tls.caBundle=dGVzdA==
```

Queue와 transport-independent CUDA 실행 코어는 GPU 없이 빌드할 수 있습니다.
CMake·C11 compiler·pthread가 필요합니다.

```sh
cmake -S runtime/shm/shm-queue -B .local/queue-build
cmake --build .local/queue-build
cmake -S runtime/shm/cuda-dispatch -B .local/dispatch-build
cmake --build .local/dispatch-build
```

## CUDA 런타임

CUDA 12.8 계열 개발 라이브러리·cuDNN 9·CMake가 필요합니다.

```sh
make build-shm
bash scripts/test-shm-training.sh "$PWD/.local/shm-build"
```

회귀 스크립트는 CUDA 헤더/라이브러리를 사용하지만 실제 GPU 실행을 대체하지 않습니다.
Containerfile은 기존 `flyt-*` 대상과 설치 경로를 유지합니다.

```sh
docker build -f images/flyt/ControlPlane.Containerfile -t vmweave-control-plane:test .
```

실제 클러스터 재현은 [별도 GPU 절차](../getting-started/gpu.md)를 따릅니다.
문서 정리나 CPU 검증 중 클러스터를 자동 변경하지 않습니다.

## CI

- 정적 검증: Python 구문·JSON 파싱·경로/CRD 일치 검사.
- CPU 제어기: 단위 테스트·Helm lint·제어기 이미지 빌드.
- 런타임 이미지: 관련 코드 main/PR 빌드 및 기존 `v*` 태그 게시 정책.
- 문서: 엄격 빌드·사이트 링크 검사 후 `main`만 Pages에 배포.

[문서 개발](documentation.md) · [구조와 이동 기록](repository.md)
