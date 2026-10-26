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
running. No-live tests also clear inherited `ODOO_` settings and select a per-test env-file fixture.
Configuration tests can replace that fixture explicitly; live markers retain their supplied runtime settings.

## Commands

```bash
uv run ruff check .          # Static-analysis gate, also run by the GitHub Actions test job
uv run mcp-test-unit         # Unit tests only
uv run mcp-test-integration  # No-live integration tests
uv run mcp-test-ci           # Quick quiet unit run; CI does not run it separately
uv run mcp-test-cov          # No-live coverage: terminal, HTML, and XML reports
uv run mcp-test-live         # Live Docker/Odoo tests; needs the target workspace running
uv run mcp-test-live-cov     # Live-stack coverage report; informational, no threshold
```

The canonical focused-local and complete-CI commands are `qualityGate.test.local` and `qualityGate.test.ci` in
[workflow metadata](../.github/github.json). Replace the local `{test_paths}` placeholder with affected modules; run complete
safety modules under [AGENTS.md](../AGENTS.md#safety-test-selection). The full suite and coverage threshold run in CI before ready.
Coverage measures only the `odoo_intelligence_mcp` package. For example, substitute
`tests/unit/tools/model/test_model_info.py` for `{test_paths}` in the local command.
Keep the no-live marker filter when selecting tests or rerunning failures.

## Fixtures

- `tests/conftest.py`: pytest fixtures such as `mock_odoo_env`, plus the Docker guard above.
- `tests/fixtures/types.py`: typed mock protocols (`MockModel`, `MockRecord`, `MockRegistry`, ...).
- `tests/fixtures/common.py`, `docker.py`, `odoo.py`: shared assertion, Docker, and Odoo mock helpers.
- `tests/fixtures/fs_index.py`: helpers for the filesystem-index (`fs` mode) tests.
