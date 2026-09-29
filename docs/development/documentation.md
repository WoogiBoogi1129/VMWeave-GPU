# 문서 작성과 Pages 배포

현재 문서는 `docs/`, 과거 원문은 `legacy/docs/`, 실험 증거는
`experiments/evidence/results/`에서 관리합니다. 같은 설명을 여러 곳에 복제하기보다 연결합니다.

## 로컬 실행

```sh
python3 -m venv .local/docs-venv
.local/docs-venv/bin/pip install -r requirements-docs.txt
make docs-serve
make docs-check
```

`mkdocs.yml`의 메뉴에 현재 안내를 등록합니다. 기존 문서 주소의 안내 페이지는
검색에서 제외하고 현재 문서 또는 역사 자료로 연결합니다.
문서는 한국어 본문과 원래 기술 식별자를 사용합니다.

## 링크와 그림

문서끼리는 상대 Markdown 링크를 사용합니다. 저장소 소스 링크도 상대 경로로 작성합니다.
빌드 hook은 `docs/` 밖의 링크가 실제 존재하는지 검사하고 GitHub 링크로 변환합니다.
기존 실험 원본은 보존 커밋으로 고정하며 코드는 현재 `main`으로 연결합니다. 역사 문서는 보존된 원문에서 작성 당시 커밋의 링크를 제공합니다.
문서 사이트에는 소스·대량 로그 전체를 복사하지 않습니다.

## 배포

GitHub Settings → Pages의 Source는 **GitHub Actions**여야 합니다.
`.github/workflows/docs.yml`은 PR에서 빌드만 수행하고, `main` push 또는
`main`의 수동 실행에서 빌드 성공 뒤 배포합니다.
배포 작업에만 `pages: write`, `id-token: write`를 주고 `github-pages` 환경을 사용합니다.
별도 PAT·SSH Secret은 필요하지 않습니다.

공개 주소: <https://WoogiBoogi1129.github.io/VMWeave-GPU/>

Pages environment의 배포 브랜치 정책이 `main`을 허용해야 합니다.
의존성은 버전을 고정합니다. 새 버전 적용 시 엄격 빌드와 링크·검색·화면을 확인합니다.
사이트 산출물 `site/`와 가상환경은 Git에서 제외합니다.

[GitHub 공식 배포 안내](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
