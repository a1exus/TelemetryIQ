.PHONY: install run test

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

run:
	.venv/bin/python -m rexy

test:
	.venv/bin/pytest tests/ -v
