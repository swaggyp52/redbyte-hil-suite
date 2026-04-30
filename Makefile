PYTHON ?= python

.PHONY: install install-dev run test lint clean

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt
	@echo "Done. Run: $(PYTHON) run.py"

install-dev: install
	$(PYTHON) -m pip install -r requirements-dev.txt

run: install
	$(PYTHON) run.py

test: install-dev
	$(PYTHON) -m pytest tests/ -v

lint:
	$(PYTHON) -m black src/ ui/ tests/
	$(PYTHON) -m isort src/ ui/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true
