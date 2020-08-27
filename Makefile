default: lint test

normal:
	isort .

lint:
	isort --check-only .
	flake8 .

test:
	coverage erase
	coverage run --source=amp_renderer -m pytest
	coverage report -m

dev:
	pip install -r requirements/dev.txt
