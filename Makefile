.PHONY: help test standup lint format check

RUFF := uvx ruff@0.16.1

help:
	@echo "test     - run the standup-digest test suite"
	@echo "standup  - print yesterday's digest JSON"
	@echo "lint     - ruff check + format check, no writes"
	@echo "format   - apply safe lint fixes, then reformat"
	@echo "check    - lint + test, the full gate"

test:
	uv run --with pytest pytest standup-digest/scripts -q

standup:
	python3 standup-digest/scripts/standup_digest.py

lint:
	$(RUFF) check .
	$(RUFF) format --check .

# check --fix runs before format: autofixes delete imports and rewrite
# annotations, which can leave a file needing reformatting.
#
# --exit-zero because `check --fix` exits non-zero whenever any finding remains
# unfixed, which would abort the recipe before `format` ever runs. This target
# fixes what it can; `make lint` is the gate that reports what's left.
format:
	$(RUFF) check --fix --exit-zero .
	$(RUFF) format .

check: lint test
