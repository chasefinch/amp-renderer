VENV_DIR := .venv
UV := $(shell command -v uv 2>/dev/null || echo $(HOME)/.local/bin/uv)

default: sync configure format lint test

clean:
	find . -name "*.pyc" -delete

sync-spec:
	@echo "Syncing configuration with global spec..."
	@nitpick fix > /dev/null || true
	@echo "...done."

configure-spec:
	@echo "Checking configuration against global spec..."
	@nitpick check
	@printf "\e[1mConfiguration is in sync!\e[0m\n\n"

sync: sync-spec
	@printf "\e[1mSync complete!\e[0m\n\n"

configure: configure-spec

format-py:
	@echo "Formatting Python docstrings..."
	@docformatter . -r --in-place --exclude bin lib dist prof build .git $(VENV_DIR) || true
	@echo "...done."
	@echo "Formatting Python files..."
	@echo "  1. Ruff Format"
	@ruff format . > /dev/null
	@echo "  2. Ruff Check (fix only)"
	@ruff check --fix-only . --quiet
	@echo "  3. Add trailing commas"
	@find . \( -path ./lib -o -path ./bin -o -path ./dist -o -path ./prof -o -path ./build -o -path ./$(VENV_DIR) -o -path ./.git \) -prune -o -name '*.py' -print0 | xargs -P 16 -0 -I{} sh -c 'add-trailing-comma "{}" || true'
	@echo "  4. Ruff Format (again)"
	@ruff format . --quiet
	@echo "  5. Ruff Check (fix only, again)"
	@ruff check --fix-only . --quiet
	@echo "...done."

format: format-py
	@printf "\e[1mFormatting done!\e[0m\n\n"

lint-py:
	@echo "Checking for Python formatting issues which can be fixed automatically..."
	@echo "  1. Ruff Format (check only)"
	@ruff format . --diff > /dev/null 2>&1 || (printf 'Found files which need to be auto-formatted. Run \e[1mmake format\e[0m and re-lint.\n'; exit 1)
	@echo "...done. No issues found."
	@echo "Running Python linter..."
	@echo "  1. Ruff Check"
	@ruff check . --quiet
	@echo "  2. Flake8"
	@flake8 .
	@echo "...done. No issues found."

lint: lint-py
	@printf "\e[1mLint passed!\e[0m\n\n"

check-py:
	@echo "Running Python type checks..."
	@ty check .
	@echo "...done. No issues found."

test:
	find . -name "*.pyc" -delete
	coverage erase
	coverage run --source=amp_renderer -m pytest --ignore=bin --ignore=lib --ignore=dist --ignore=prof --ignore=build
	coverage report -m --fail-under 90

install:
	$(UV) pip install -r requirements/develop.txt

setup:
	@if [ ! -x "$(UV)" ]; then curl -LsSf https://astral.sh/uv/install.sh | sh; fi
	$(UV) venv --prompt "amp-renderer" $(VENV_DIR)
	$(UV) pip install --python $(VENV_DIR) -r requirements/develop.txt
	@printf "\n\e[1mSetup complete!\e[0m\n\n"
	@echo "Activate the virtual environment with:"
	@echo
	@echo "	source $(VENV_DIR)/bin/activate"
	@echo

.PHONY: default clean sync sync-spec configure configure-spec \
        format format-py lint lint-py check-py test install setup
