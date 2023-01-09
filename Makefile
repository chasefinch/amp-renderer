default: format lint test

format:
	@echo "Converting imports to relative imports where possible..."
	@find . \( -path ./lib -o -path ./bin -o -path ./dist -o -path ./prof -o -path ./build -o -path ./git \) -prune -o -name '*.py' -exec absolufy-imports --never {} \;
	@echo "...done."

	@echo
	@echo "Removing unnecessary imports..."
	@autoflake . -r --in-place --remove-all-unused-imports --exclude="./bin/*,./lib/*,./dist/*,./prof/*,./build/*,.git/*"
	@echo "...done."

	@echo
	@echo "Sorting imports..."
	@isort .
	@echo "...done."

	@echo
	@echo "Formatting docstrings..."
	@# --wrap-descriptions is 72 by default; Doesn't seem necessary to shorten it that far
	@docformatter . -r --in-place --wrap-descriptions=79 --exclude bin lib dist prof build .git
	@echo "...done."

	@echo
	@echo "Formatting Python files..."
	@black . --line-length 99 --target-version py38 --quiet
	@# Add trailing commas to dangling lines and function calls
	@find . \( -path ./lib -o -path ./bin -o -path ./dist -o -path ./prof -o -path ./build -o -path ./git \) -prune -o -name '*.py' -exec add-trailing-comma --py36-plus {} \;
	@# Format again after adding trailing commas
	@black . --line-length 99 --target-version py38 --quiet
	@echo "...done."
	@echo

lint:
	@echo "Checking for Python formatting issues which can be fixed automatically..."
	@black . --experimental-string-processing --line-length 99 --target-version py38 --check --quiet || (printf 'Found files which need to be auto-formatted. Run \e[1mmake format\e[0m and re-lint.\n'; exit 1)
	@isort . --check --quiet || (printf 'Found files which need to be auto-formatted. Run \e[1mmake format\e[0m and re-lint.\n'; exit 1)
	@echo "...done. No issues found."

	@echo
	@echo "Running Python linter..."
	@flake8 . && echo "...done. No issues found."
	@echo

test:
	find . -name "*.pyc" -delete
	coverage erase
	coverage run --source=amp_renderer -m pytest --ignore=bin --ignore=lib --ignore=dist --ignore=prof --ignore=build
	coverage report -m --fail-under 90

install:
	${CURDIR}/bin/pip install -U pip wheel
	${CURDIR}/bin/pip install -r requirements/develop.txt --use-deprecated=legacy-resolver

.PHONY: default format lint test install
