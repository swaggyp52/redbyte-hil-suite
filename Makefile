.PHONY: install run test lint clean

install:
	pip install --upgrade pip
	pip install -r requirements.txt
	python -m playwright install chromium
	@echo "Done. Run: python run.py"

run:
	python run.py

test:
	pytest tests/ -v

lint:
	black src/ ui/ tests/
	isort src/ ui/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true
