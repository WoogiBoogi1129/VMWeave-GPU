# 원본에서 추출한 최소 증거 fixture

`stage1/`은 기존 Stage 1 판정 테스트가 읽는 JSON 4개이고, `stage2/`는 독립 실행 3회의
trace·상태·출력 배열·hash 등 `verify_stage2.verify()`가 실제 읽는 파일 24개다.
모두 원본 bytes를 그대로 복사했으며 내용 축약·재생성은 하지 않았다.

[출처 manifest](provenance.json)는 파일별 원본 경로, 원본을 포함하는 커밋과 SHA256을 기록한다.
`scripts/check-repository.py`가 복사본을 검사한다. 원본은 기존 `experiments/evidence/results/`에 보존한다.
fixture 갱신 시 판정 근거와 출처도 갱신해야 하며 기존 결과를 재작성하지 않는다.

CPU 제어 테스트는 이 fixture를 읽으므로 전체 실험 결과 디렉터리가 필요하지 않다.
검증 함수 자체는 여전히 `experiments/evidence/`의 소스에서 가져온다.
이는 증거 입력의 분리이며 실험 도구 소스까지 모두 분리했다는 의미는 아니다.
