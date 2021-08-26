default: lint test

format:
	isort .

lint:
	isort --check-only .
	flake8 .

test:
	coverage erase
	coverage run --source=amp_renderer -m pytest
	coverage report -m

develop:
	pip install -r requirements/develop.txt
