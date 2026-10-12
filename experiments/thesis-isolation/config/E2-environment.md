# E2 실행 환경 준비

이 기록은 환경 준비에 한정한다. 실제 Guest의 GPU 호환성, MLP 정확성 및 E2 본실험 결과가 아니다.

## 수정 이유

초기 `iso-e2-pilot-a`는 `artifacts/flyt-guest-bundle.tar.gz`에서 존재하지 않는
`opt/torch-venv`, `opt/flyt-cuda-libs`를 추출하려다 실패했다.
기존 실패 기록은 그대로 보존했다. 제품 코드는 변경하지 않았다.

정지된 로컬 `flyt-pytorch-dev` 컨테이너에 남아 있던 두 디렉터리를 복사해
새 번들을 구성했다. 기존 검증 자료의 `libnuma.so.1`, `libgomp.so.1`도
CUDA 라이브러리 디렉터리에 포함했다. 원본 컨테이너를 시작하지 않았다.

## 산출물과 검증

- 실제 대용량 번들: `.local/thesis-isolation-20261012/guest-python-cuda.tgz` (로컬 전용).
- 경로·SHA256·버전: [e2-environment.json](e2-environment.json).
- 환경 검사 결과: [validation.json](../results/20261012-e2-environment/validation.json).
- 동적 라이브러리 의존성: [dependencies.txt](../results/20261012-e2-environment/dependencies.txt).
- 실행 전 검사기: [environment.py](../runner/environment.py).

검증은 네트워크와 GPU 장치 전달 없이 로컬 컨테이너에서 수행했다.
Python 3.10.12, PyTorch 2.11.0+flyt.cu128, CUDA 12.8, NumPy 2.2.6의
import 및 CPU 행렬 계산을 확인했다. GPU 계산 성공을 의미하지 않는다.
Guest의 `/usr/bin/python3`는 Python 3.10이어야 하며 Guest에서의 의존성 검사는
다음 준비 단계에서 별도로 확인해야 한다.

저장소 루트에서 번들 재검증:

```sh
python3 experiments/thesis-isolation/runner/environment.py
```

번들 재생성은 보존된 `bundle-stage`에서 수행한다. 새 번들의 해시를 검증·기록하기
전에는 기존 manifest를 임의로 바꾸지 않는다.

```sh
tar -czf .local/thesis-isolation-20261012/guest-python-cuda.tgz \
  -C .local/thesis-isolation-20261012/bundle-stage opt/torch-venv opt/flyt-cuda-libs
```

`runner/e2.py`는 VM 생성 전에 번들 해시·내부 경로를 검사하며 실행마다 시각 기반
새 ID를 사용한다. E2는 여전히 예비 실행 단계이며 두 VM의 세 조건 본실험 자동화가
완료된 상태는 아니다. 이번 환경 준비에서는 이 실행기를 실행하지 않았다.
