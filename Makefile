.PHONY: install test check doctor-build doctor-test doctor-health run clean

PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

install:
	$(PIP) install -e ".[test]"

doctor-build:
	$(PYTHON) -m compileall -q urirun_service_chat

doctor-test:
	$(PYTHON) -m pytest -q tests

doctor-health:
	$(PYTHON) -c "import urirun_service_chat"

test: doctor-test

check: doctor-test doctor-health

run:
	$(PYTHON) -m urirun_service_chat.core

clean:
	rm -rf build dist *.egg-info .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
