# v0.5.9 공개 배포물·현재 노드 업데이트 검증

2026-11-08 공개된 v0.5.9 이미지와 Operator chart 0.5.9,
Device Plugin v0.1.1 패키지를 현재 `gpu-4` 노드에 적용하고 실제 VM에서 재검증했다.
소스 commit은 `b0f73c16b84f65887953118f33ff08b82fc403af`이며, main과 릴리스 태그에 반영했다.
[전체 릴리스 기록](../../v0.5.9.json)과 [Device Plugin 배포물](../../device-plugin-v0.1.1.json)을 참조한다.

## 적용 상태

- 중앙 Helm `vmweave`: revision16, chart0.5.9. `nested`: revision5, chart0.5.9.
  Controller/Webhook 4개 모두 새 공개 digest로 Ready다.
- VM `vmweave-test-b/dp-dev-20261105`: Running/Ready, 새 Channel Ready.
  Worker·helper·hook을 v0.5.9로 교체하고 VM 내부 Guest package를 새 버전으로 설치했다.
- 내부 Helm `vmweave-device-plugin`: revision2, chart0.1.1. 실제 GPU 자원 `vmweave.io/gpu: 1` 등록.
- 새 Profile/Request는 `dp-dev-20261105-v059`다. VM UID, root/SHM PVC, compute25%·memory1024MiB를 유지했다.
  기존 Profile/Request는 롤백 구성 확인용으로 보존했다.
- GPU 작업 종료 후 기존 Channel의 정상 회수·Stopped를 확인하고 새 immutable 설정으로 Channel을 재생성했다.
  이전 Channel UID의 VM binding annotation이 남아 새 연결을 막았으므로, VMI 부재·이전 회수 증거를 확인하고
  UID/resourceVersion 조건으로 이전 binding 정보만 제거했다. finalizer나 완료 증거를 강제 변경하지 않았다.
  [전환 근거](stale-binding-cleanup.json), [이전 연결 회수](upgrade-stopped-channel.json)를 보존했다.

Guest library SHA256은 `3b3644f42ae3d075c08c22e2578e59553e29c5a446f65cf41f33ad68a070a4a9`다. 후보 실험의 Guest hash와 다르며,
공개 패키지의 `guest-identity.txt`, 설치 파일, Broker status와 Plugin 설정이 모두 일치한다.
공개 OCI 이미지 label의 소스 revision을 확인했고, chart 내용은 저장소 소스와 비교했다.
[일반 Runtime Guest와 Plugin Guest의 라이브러리 hash](guest-package-equivalence.json)도 일치한다.
Plugin의 배포 archive를 CRI store에 가져오면 manifest digest가 달라질 수 있어
[공개 digest·실행 digest·image ID 매핑](plugin-image-identities.json)을 기록했다.
이미지 ID는 공개 archive의 이미지 ID와 일치한다. OCI chart와 릴리스 첨부 chart의 파일 hash도 일치한다.

## 실제 공개 이미지의 학습 결과

공식 PyTorch `2.11.0+cu128` 이미지를 그대로 사용했다. cuDNN 활성화,
`DISABLE_ADDMM_CUDA_LT`와 `TORCH_CUDNN_V8_API_DISABLED` 미설정으로 실행했다.
Guest initContainer도 공개 배포물의 이미지이며 후보 `.so` ConfigMap 주입을 사용하지 않았다.

| 시험 | 결과 | 비교 텐서 | 최대 절대 차이 |
|---|---|---:|---:|
| LSTM 5 step | 통과 | 36 | 3.516674041748047e-06 |
| 연속 학습 128 step | 통과 | 7 | 4.470348358154297e-07 |
| 새 Pod에서 96 step 재개 | 통과 | 7 | 0.0 |
| 기본 Lt 경로 MLP | 통과 | 22 | 4.284083843231201e-08 |
| CUDA 행렬곱 | 통과 | assert_close | — |

모든 비교는 rtol1e-4/atol1e-6이며 [별도 CPU 검산](offline-tensor-audit.json)도 72개 텐서의
유한성·정확성을 통과했다. 재개 시험은 step32 checkpoint를 새 Pod에서 읽어 step128까지 실행한 뒤
중단 없는 GPU 학습과 최종 가중치·검증 logits를 비교했다.
[재개 학습 중 GPU 관측](gpu-observation.json)에서 호스트 PID와 Worker 세션 PID를 연결했다.
첫 관측은 관리자 Pod의 PID namespace에서 대응 프로세스를 얻지 못했다. 해당 검증 중단은
[기록](verify-live.log)에 보존했고, 호스트에서 직접 관측해 실제 GPU 연결을 확인했다.
연속 학습 자체는 처음 실행에서 성공했다.

CPU·GPU 검증 정확도는 모두 9.375%, GPU 검증 loss는 2.30075121다.
이번 시험은 연산의 정상 실행과 정확성·재개 검증이며, 유의미한 모델 수렴이나 처리량 비교가 아니다.
FP32 단층·단방향 LSTM과 해당 Linear 경로를 검증했으며 CNN·AMP·분산 학습 또는 모든 RNN 설정을 주장하지 않는다.

## 유지·정리한 구성

[보존 검사](preservation.json)에서 기존 Running 내부 Kubernetes control-plane VM의 UID·spec·Running 상태를 확인했다.
기존 `Draining` Channel 3개는 이전부터 회수가 막힌 상태였으며 spec·UID를 유지했다.
대상은 `vmweave-nested-k8s/vw-k8s-worker-01`, `vmweave-test-a/vmweave-k8s-01`,
`vmweave-test-a/vram-pair-v2-r1-ab-a`다. 이 비활성 실행들을 새 버전으로 전환했다고 주장하지 않는다.
Kubernetes·KubeVirt·HAMi·DRA·GPU Operator는 이번 Runtime 릴리스 변경 대상이 아니어서 유지했다.

검증용 내부 namespace와 빌드/검사용 관리자 Pod를 삭제했다. 학습 세션은 회수됐고,
업데이트한 VM은 **Running**, Channel은 **Ready**로 남겨 사용할 수 있게 했다.
[검사 후 GPU 상태](gpu-after-tests.json), [Broker 상태](broker-after-tests.json)를 기록했다.

## 재검증

```sh
(cd deploy/releases/evidence/v0.5.9 && sha256sum -c SHA256SUMS)
python3 experiments/rnn-default/audit_tensors.py --published \
  --results deploy/releases/evidence/v0.5.9/training
```

원시 Pod 선언·종료 상태·CPU/GPU 텐서·checkpoint는 `training/`에 보존했다.
[CI 실행 기록](actions-final-source.json)은 이미지·chart·Plugin·CPU control-plane·문서·정적 검사 성공을 담는다.
새 클러스터 전체 설치 검증은 포함하지 않는다.
