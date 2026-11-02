.PHONY: install test evaluate verify check-report

install:
	.venv/bin/pip install -e ".[eval,dev]"

test:
	.venv/bin/python -m pytest -q

evaluate:
	.venv/bin/python scripts/evaluate_pipeline.py

check-report:
	.venv/bin/python scripts/evaluate_pipeline.py --check

verify: test check-report
	@echo "Verification complete: tests pass and the committed report is current."
