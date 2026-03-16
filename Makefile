.PHONY: build up down logs restart install

install:
	python3 -m venv .venv
	.venv/bin/pip install -e .

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

restart:
	docker compose down && docker compose up -d
