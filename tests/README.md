# Odoo Intelligence MCP Test Suite

The rules for writing tests live in [AGENTS.md](../AGENTS.md#test-rules). This file maps the suite and its commands.

## Layout

```
tests/
├── conftest.py        # Shared pytest fixtures and the no-live-stack Docker guard
├── fixtures/          # Helper package: mocks, protocol types, Docker and fs-index helpers
├── unit/
│   ├── core/          # Environment resolution, registry, pagination utilities
│   ├── models/        # Data models and responses
│   ├── server/        # Server-level behavior such as argument aliases
│   ├── services/      # Service layer
│   ├── tools/         # Tool implementations, grouped like src/odoo_intelligence_mcp/tools
│   └── utils/         # Docker, error, response, and security utilities
└── integration/       # Server handlers, MCP protocol and stdio, tool contracts; some need a live stack
```

## Markers

- `requires_docker`: needs a live Docker daemon.
- `requires_odoo`: needs a live Odoo container or workspace.

Tests without either marker never reach the host Docker daemon: `tests/conftest.py` answers `docker` subprocess calls as
"no such container" and turns container start-up waits into no-ops, so results match CI whether or not a local stack is
running.

## Commands

```bash
uv run mcp-test              # Default no-live-stack gate for local and PR validation
uv run mcp-test-unit         # Unit tests only
uv run mcp-test-integration  # No-live integration tests
uv run mcp-test-ci           # Quick quiet unit run; CI does not run it separately
uv run mcp-test-cov          # No-live coverage: terminal, HTML, and XML reports, 75% minimum
uv run mcp-test-cov-ci       # What the GitHub Actions `test` job runs: same scope and minimum, no HTML
uv run mcp-test-live         # Live Docker/Odoo tests; needs the target workspace running
uv run mcp-test-live-cov     # Live-stack coverage report; informational, no threshold
```

Coverage measures only the `odoo_intelligence_mcp` package. To select tests by hand:

```bash
uv run pytest tests/unit/tools/model/test_model_info.py -v
uv run pytest -m "not requires_docker and not requires_odoo"
uv run pytest --lf
```

## Fixtures

- `tests/conftest.py`: pytest fixtures such as `mock_odoo_env`, plus the Docker guard above.
- `tests/fixtures/types.py`: typed mock protocols (`MockModel`, `MockRecord`, `MockRegistry`, ...).
- `tests/fixtures/common.py`, `mocks.py`, `docker.py`, `odoo.py`: shared assertion and mock helpers.
- `tests/fixtures/fs_index.py`: helpers for the filesystem-index (`fs` mode) tests.
