.PHONY: install run test help

help:
	@echo "Usage:"
	@echo "  make install   Install dependencies into .venv"
	@echo "  make run       Start TelemetryIQ (auto-discovers PlayStation on LAN)"
	@echo "  make test      Run tests"
	@echo ""
	@echo "Options (pass as env vars):"
	@echo "  PS_IP=192.168.1.42 make run   Set PlayStation IP manually"
	@echo "  GT7_HEARTBEAT_TYPE=A make run  Telemetry format: A, B (default), ~"

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

run:
	.venv/bin/python -m rexy

test:
	.venv/bin/pytest tests/ -v
