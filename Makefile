default: normalize lint test

normalize:
	isort -rc .

lint:
	flake8 .

test:
	coverage erase
	coverage run --source=amp_renderer -m pytest
	coverage report -m

requirements:
	pip install -r requirements/development.txt
