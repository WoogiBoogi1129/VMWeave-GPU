# VMWeave-GPU 개발 안내

현재 개발 기준은 `main`입니다. 큰 변경은 검토 가능한 커밋으로 나누고, 실험 결과의
성공·실패·제외 내역을 함께 보존합니다. 구현 완료와 실제 GPU 검증을 구분합니다.

- [소스 빌드와 테스트](docs/development/index.md)
- [문서 작성·Pages 배포](docs/development/documentation.md)
- [디렉터리 책임과 이동 기록](docs/development/repository.md)
- [실험 증거 정책](docs/evaluation/artifacts.md)

변경 설명에는 문제, 변경 후 동작, 실행한 검증과 미실행 범위를 포함하세요.
문서 변경은 `make docs-check`, 제어기 변경은 `make operator-check`와 `make test-control`을 실행합니다.
CUDA 관련 변경은 개발 문서의 빌드·회귀 검사를 추가합니다.

과거 결과를 새로운 코드로 생성한 결과처럼 수정하지 않습니다. 재실험은 새 식별자와
디렉터리를 사용하고 코드 SHA, 이미지 digest, 입력, 환경, 판정 근거를 기록합니다.
실제 클러스터 시험은 CPU 단위 테스트나 문서 빌드와 별도로 실행합니다.
