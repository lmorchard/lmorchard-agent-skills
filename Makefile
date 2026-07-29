.PHONY: help test standup

help:
	@echo "test     - run the standup-digest test suite"
	@echo "standup  - print yesterday's digest JSON"

test:
	uv run --with pytest pytest standup-digest/scripts -q

standup:
	python3 standup-digest/scripts/standup_digest.py
