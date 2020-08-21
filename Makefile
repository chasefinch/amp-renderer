default: normal lint test

normal:
	isort .

lint:
	flake8 .

test:
	coverage erase
	coverage run --source=amp_renderer -m pytest
	coverage report -m

requirements:
	pip install -r requirements/development.txt
