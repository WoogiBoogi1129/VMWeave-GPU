# CPU review 검증

review는 중앙 Go Operator의 검증 모드이며, GPU 실행 전 반드시 설치해야 하는 별도 제어기가 아닙니다.
[공통 중앙 설치](install.md)에서 `deploy/examples/vmweave/review.json` 설정을 사용합니다.
review는 VM/Worker를 실행하거나 allocation/finalizer를 만들지 않습니다.

```sh
python3 scripts/operator/review-smoke.py --namespaces team-a team-b \
  --output .local/vmweave-review.json
```

동일한 이름의 Channel을 두 namespace에 만들고, 독립 상태·할당 없음·finalizer 없음·상태 갱신 안정성을
검증한 뒤 자신이 만든 UID의 객체만 제거합니다. 실제 review Operator가 필요합니다.

개발 검증:

```sh
cd operator
make check
cd ..
python3 -m unittest discover -s tests/control -v
```

Python 테스트는 이전 helper/행동 계약의 회귀 검사입니다. 새 Go Operator의 검증을 대신하지 않습니다.
과거 namespace별 Python 설치는 [기존 이력](../../legacy/docs/installation/INSTALLATION_REPORT_2026-09-22.md)에 보존합니다.
