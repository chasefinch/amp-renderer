default: lint test

format:
	isort . --skip lib --skip bin
	docformatter . --in-place --wrap-descriptions=79 -r --exclude="./bin/*,./lib/*,./node_modules/*,*/migrations/*"
	autoflake . --in-place -r --exclude="./bin/*,./lib/*,./node_modules/*,*/migrations/*"
	autopep8 . --in-place -r --exclude="./bin/*,./lib/*,./node_modules/*,*/migrations/*"

lint:
	flake8 .

test:
	coverage erase
	coverage run --source=amp_renderer -m pytest --ignore=bin --ignore=lib
	coverage report -m

update:
	${CURDIR}/bin/pip install -U pip wheel
	${CURDIR}/bin/pip install -r requirements/develop.txt --use-deprecated=legacy-resolver

.PHONY: default format lint test update
