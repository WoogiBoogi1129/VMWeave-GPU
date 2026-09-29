# 설치와 시작

목적에 맞는 경로를 선택하세요. 현재 배포는 연구 환경을 전제로 합니다.

| 목적 | 필요한 환경 | 안내 |
|---|---|---|
| 문서 읽기·수정 | Python 3.11 이상 | [문서 개발](../development/documentation.md) |
| 제어기 단위 테스트 | Python 3 | [개발 검증](../development/index.md) |
| CPU review 실클러스터 | Kubernetes·Helm·admission 권한·KubeVirt CRD | [CPU 제어기 설치](cpu-control-plane.md) |
| VM GPU 실행 | NVIDIA GPU·CUDA·HAMi·KubeVirt·로컬 PVC·Guest 환경 | [GPU 준비](gpu.md) |

## 소스 받기

```sh
git clone https://github.com/WoogiBoogi1129/VMWeave-GPU.git
cd VMWeave-GPU
python3 -m unittest discover -s tests/control -v
```

모든 명령은 특별한 안내가 없으면 저장소 루트에서 실행합니다.
기존 `flyt-k8s-poc` 클론도 origin을 새 주소로 지정해 계속 사용할 수 있습니다.

컨테이너·CRD·환경변수에 남은 `flyt`는 현재 호환 식별자입니다.
문서의 프로젝트 이름과 달라도 임의로 변경하지 마세요.
