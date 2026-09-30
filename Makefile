.DEFAULT_GOAL := help
.PHONY: help build-shm render docs-serve docs-check test-control check-layout
DOCS_PYTHON ?= .local/docs-venv/bin/python
help:
	@echo 'VMWeave-GPU: see docs/overview/status.md for the supported and validated scope.'
	@echo 'make build-shm    Configure/build the SHM runtime locally (explicit action)'
	@echo 'make render ARGS="..."    Legacy SHM renderer; new installs use docs/getting-started/install.md'
	@echo 'make docs-check / docs-serve    Build or preview the documentation'
	@echo 'make test-control / check-layout    CPU tests and repository checks'
build-shm:
	cmake -S runtime/shm -B .local/shm-build -DCMAKE_BUILD_TYPE=Release
	cmake --build .local/shm-build --parallel 2
render:
	python3 scripts/render-shm.py $(ARGS)
docs-serve:
	$(DOCS_PYTHON) -m mkdocs serve
docs-check:
	$(DOCS_PYTHON) -m mkdocs build --strict
	$(DOCS_PYTHON) scripts/check-site.py
test-control:
	python3 -m unittest discover -s tests/control -v
check-layout:
	python3 scripts/check-repository.py

.PHONY: operator-check operator-build
operator-check:
	$(MAKE) -C operator check
operator-build:
	$(MAKE) -C operator build
