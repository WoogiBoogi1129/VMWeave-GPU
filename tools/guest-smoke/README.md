# 배포용 Guest GPU smoke

`guest_gpu_smoke.c`는 Guest 배포 이미지에 포함하는 작은 CUDA/PTX 검증 프로그램이다.
현재 이미지 빌드는 이 경로를 사용한다. 코드 동작은 분리 전과 동일하다.

초기 원본은 `experiments/evidence/guest_gpu_smoke.c`이며 이동·수정하지 않았다.
[출처 manifest](provenance.json)에 원본 커밋·경로와 복사본 SHA256을 기록한다.
`scripts/check-repository.py`는 배포 소스의 hash를 검사한다. 소스를 의도적으로 변경할 때는
manifest와 검증 기록도 함께 갱신하고 과거 실험 원본은 수정하지 않는다.

컨테이너 빌드 입력과 [수동 Guest 준비](../../docs/getting-started/guest-images.md)는 이 파일을 참조한다.
메모리·compute 특화 probe와 과거 실행기는 계속 `experiments/evidence/`에서 관리한다.
출처가 같다는 사실은 새로운 GPU 실행 검증을 의미하지 않는다.
