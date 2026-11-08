# 기본 CUDA 라이브러리 경로의 LSTM 학습

목표: 공식 PyTorch 이미지의 `nn.LSTM` 학습을 cuDNN 비활성화 또는
`DISABLE_ADDMM_CUDA_LT=1` 없이 VMWeave에서 실행하고 정확성을 검증한다.

2026-11-08 후보 Guest/Worker에서 기본 경로의 LSTM 학습·CPU 검산·체크포인트 재개가
통과했다. [결과 보고서](results/20261108/REPORT.md)에 최초 실패와 수정 과정,
검증 수치 및 지원 범위를 기록했다. 이 보고서는 후보 실험 기록이다. 후속 [v0.5.9 공개 배포물 검증](../../deploy/releases/evidence/v0.5.9/README.md)에서
게시된 Guest/Worker와 Device Plugin v0.1.1을 설치해 다시 확인했다.

## 고정 시험

- MNIST 앞 1,024개 학습 이미지와 256개 시험 이미지. 원본 출처/hash는 `data/manifest.json`.
- 이미지 행을 시퀀스로 사용: `[16,28,28]`, 단층·단방향 LSTM hidden32 + Linear10.
- FP32, TF32 off, dropout0, SGD lr0.01, foreach/fused off. seed20261108.
- 첫 16개 실제 이미지로 5 step. step1/5의 출력·상태·loss·입력/파라미터 gradient·갱신 파라미터를
  CPU 참조와 rtol1e-4/atol1e-6으로 비교한다. CPU fallback은 사용하지 않는다.
- 별도 후속 시험: 변경 batch의 2 epoch 학습, 체크포인트 재개, 새 Pod 재현,
  MLP·기초 CUDA 회귀, 회수 및 재사용.
- 최초 실패와 모든 수정 후 시도를 별도로 보존한다. 함수 진입·반환과 심볼 연결 기록을 구분한다.

## 경계

새 cuDNN RNN v8 및 cuBLASLt 중계는 Worker의 실제 라이브러리를 호출한다.
입력 포인터는 세션의 할당 handle+offset으로 전달하고 descriptor는 타입별 원격 ID로 관리한다.
현재 RNNData FP32·batch≤1024, tensor rank≤8, cuBLASLt FP32 host scalar/열 우선 layout 범위다.
미지원 형식은 명시적 오류를 반환한다. 이 범위 밖의 API 전체 지원을 주장하지 않는다.

## 실행

기존 CNN runner와 같은 SSH 연결 JSON을 사용한다. 연결 정보는 `.local/`에 둔다.
`runner/run.py prepare`는 새 namespace와 immutable 코드 ConfigMap을 만들며,
`run --name ... --case lstm --guest-library ...`는 후보 Guest를 별도 ConfigMap으로 주입한다.
Worker 후보는 시험용 VM/Profile/Channel에서만 사용한다. 실제 이미지 digest와 소스 hash를 기록한다.
기존 공식 이미지의 PyTorch/CUDA 파일을 교체하지 않는다.

보존된 증거의 검사:

```sh
python3 experiments/rnn-default/validate.py
# PyTorch가 설치된 CPU 환경에서 원시 텐서를 다시 검산
python3 experiments/rnn-default/audit_tensors.py
```
