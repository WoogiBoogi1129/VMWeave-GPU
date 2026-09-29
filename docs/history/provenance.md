# 출처와 인용

VMWeave-GPU는 Flyt/Cricket 기반 GPU 가상화 실험에서 발전했습니다.
이전 Flyt 기준 커밋은 `596a86939bae125d127a9ed6f70d92c332f47644`이며,
이 저장소의 MPS 기준 버전은 `f6552296f6e355c70ddcd8133857703b3ae622ee`입니다.
현재 기본 경로는 SHM 전용이며 이전 RPC 구현은 `legacy/rpc/`에 보존합니다.

- [원본 저작권 및 MIT License](../../LICENSE)
- [NOTICE](../../NOTICE)
- [이전 provenance 기록](../../legacy/docs/PROVENANCE.md)
- [기준 Flyt 소스](https://github.com/WoogiBoogi1129/flyt_custom_for_k8s)

기존 코드·선행 아이디어와 이 프로젝트에서 추가한 설계·구현·검증을 구분합니다.
CUDA/cuDNN, HAMi, PyTorch, Kubernetes, KubeVirt는 각 프로젝트의 조건을 따릅니다.
저장소 이름 변경만으로 원본 기여의 귀속이 달라지지 않습니다.

논문 서지 정보가 확정되기 전에는 저장소와 사용 커밋을 인용합니다.
실험 결과는 해당 보고서의 실행 커밋·이미지·체크섬까지 연결합니다.
