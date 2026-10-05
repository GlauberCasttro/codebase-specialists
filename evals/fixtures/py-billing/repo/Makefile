PY ?= python3
export PYTHONPATH := src

.PHONY: test lint fmt coverage check-money

test:
	$(PY) -m unittest discover -s tests -v

lint: check-money
	ruff check src tests
	ruff format --check src tests

fmt:
	ruff format src tests

check-money:
	$(PY) scripts/check_no_float_money.py src/billing

coverage:
	coverage run -m unittest discover -s tests
	coverage report
