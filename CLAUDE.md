## Quick Reference

- **Language**: Python (3.10+)
- **Format**: `make format` (ruff + docformatter + add-trailing-comma)
- **Lint**: `make lint` (ruff check + flake8/wemake)
- **Test**: `make test` (pytest + coverage, 90% minimum)
- **All**: `make` (sync, configure, format, lint, test)
- **Config sync**: `make sync` / `make configure` (nitpick)

## Skills & Tools

- Ruff for formatting and linting (replaces black, isort, autoflake, absolufy-imports)
- wemake-python-styleguide via flake8 for additional style checks
- docformatter for docstring wrapping
- add-trailing-comma for trailing commas
- nitpick for configuration syncing against remote style spec
- ty for type checking
- coverage + pytest for testing
