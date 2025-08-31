# Odoo Intelligence MCP Test Suite

## Overview

This test suite ensures the reliability, security, and performance of the Odoo Intelligence MCP Server. Tests are organized by type and module to facilitate maintenance and debugging.

## Test Structure

```
tests/
├── unit/               # Unit tests for individual components
│   ├── core/          # Core functionality (env, utils)
│   ├── models/        # Data models and responses
│   ├── services/      # Service layer logic
│   ├── tools/         # Individual tool implementations
│   └── utils/         # Utility functions
├── integration/       # Integration tests
│   ├── test_server_integration.py    # Server handler tests
│   ├── test_docker_failure_modes.py  # Docker failure scenarios
│   ├── test_security_boundaries.py   # Security tests
│   └── test_mcp_protocol.py         # MCP protocol compliance
├── fixtures.py        # Shared test fixtures
├── helpers.py         # Test helper utilities
└── conftest.py       # Pytest configuration

```

## Running Tests

### All Tests
```bash
uv run mcp-test
```

### Unit Tests Only
```bash
uv run pytest tests/unit/ -v
```

### Integration Tests Only
```bash
uv run pytest tests/integration/ -v
```

### With Coverage
```bash
uv run mcp-test-cov
```

### Specific Test File
```bash
uv run pytest tests/unit/tools/model/test_model_info.py -v
```

### Failed Tests Only
```bash
uv run pytest --lf
```

## Test Categories

### 1. Unit Tests

Unit tests verify individual components in isolation using mocks.

#### Core Tests
- **test_env.py**: Environment management and Docker registry
- **test_utils.py**: Utility functions and pagination
- **test_docker_registry.py**: Registry iteration patterns

#### Service Tests
- **test_field_analyzer_service.py**: Field analysis logic
- **test_model_inspector_service.py**: Model inspection
- **test_odoo_analyzer_service.py**: Odoo-specific analysis

#### Tool Tests
Each tool has comprehensive tests covering:
- Valid input handling
- Invalid input validation
- Error scenarios
- Edge cases
- Response format validation

### 2. Integration Tests

Integration tests verify component interaction and system behavior.

#### Critical Tests
- **test_server_integration.py**: Server handler integration
- **test_docker_failure_modes.py**: Docker connection failures
- **test_security_boundaries.py**: Security vulnerability prevention
- **test_mcp_protocol.py**: MCP protocol compliance

### 3. Performance Tests

Performance tests ensure acceptable response times and resource usage.

- Pagination handling for large datasets
- Concurrent request handling
- Memory usage under load
- Timeout behavior

## Test Patterns

### Using Test Helpers

**See real Docker failure test examples:**
- `tests/integration/test_docker_failure_modes.py::test_container_not_found()`
- `tests/integration/test_docker_failure_modes.py::test_docker_timeout_handling()`

### Testing Error Scenarios

**See real error scenario examples:**
- `tests/unit/services/test_base_service.py::test_validate_model_exists_model_not_found()`  
- `tests/unit/tools/model/test_model_info.py::test_get_model_info_nonexistent_model()`

### Testing Pagination

**See real pagination test examples:**
- `tests/unit/tools/analysis/test_analysis_query.py::test_analyze_performance_with_pagination()`
- `tests/unit/core/test_utils.py::test_paginate_list()` for pagination logic

## Mock Data

Mock data is configured in `conftest.py` and provides realistic Odoo responses:

- Model structures (fields, methods, inheritance)
- Field metadata (type, required, computed)
- Relationships (M2O, O2M, M2M)
- View definitions
- Security rules

## Security Testing

Security tests verify protection against:

1. **Code Injection**: Preventing execution of malicious code
2. **Path Traversal**: Restricting file access to Odoo directories
3. **Command Injection**: Sanitizing shell command inputs
4. **Data Exfiltration**: Preventing unauthorized data access
5. **DoS Attacks**: Rate limiting and timeout protection

## Coverage Requirements

- **Target**: 80% minimum overall coverage
- **Critical Paths**: 100% coverage for security-sensitive code
- **New Code**: All new features must include comprehensive tests

## Best Practices

### 1. Test Naming
```python
# Test name should be descriptive: test_<component>_<scenario>_<expected_outcome>
def test_model_info_invalid_name_returns_error() -> None:
    ...
```

### 2. Arrange-Act-Assert Pattern
**See real AAA pattern examples:**
- `tests/unit/tools/model/test_model_info.py::test_get_model_info_basic()`
- `tests/unit/services/test_base_service.py` for structured test patterns

### 3. Comprehensive Assertions
**See real assertion examples:**
- `tests/fixtures/common.py::assert_model_info_response()` - Comprehensive validation
- `tests/unit/tools/model/test_model_info.py` - Multiple assertion patterns

### 4. Error Message Testing
**See real error testing examples:**
- `tests/unit/services/test_base_service.py::test_validate_model_exists_model_not_found()`
- `tests/fixtures/common.py::assert_error_response()` - Error validation helper

## Debugging Failed Tests

### 1. Run with verbose output
```bash
uv run pytest tests/failing_test.py -vvs
```

### 2. Use pytest debugging
```bash
uv run pytest tests/failing_test.py --pdb
```

### 3. Check test logs
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 4. Isolate the test
```bash
uv run pytest tests/failing_test.py::TestClass::test_method -v
```

## Working Import Examples

### Common Test Helpers
**See real helper usage examples:**
- `tests/unit/tools/model/test_model_info.py` - Uses `assert_model_info_response()`
- `tests/fixtures/common.py` - All available assertion helpers
- `tests/conftest.py` - Fixture definitions and usage patterns

### Docker Testing Helpers
**See real Docker test examples in:**
- `tests/unit/utils/test_docker_utils.py::test_get_container_names_success()`
- `tests/integration/test_docker_integration.py::test_docker_container_operations()`
- `tests/fixtures/docker.py` for all Docker test utilities

### Mock Utilities
**See real mock examples in:**
- `tests/unit/tools/model/test_model_info.py::test_get_model_info_basic()` - MockOdooEnvironment usage
- `tests/fixtures/mocks.py` - All available mock utilities  
- `tests/fixtures/odoo.py` - Odoo-specific mock helpers

### Type Definitions
**See real type usage examples in:**
- `tests/unit/services/test_base_service.py` - MockOdooEnvironment usage
- `tests/fixtures/types.py` - All available type protocols (MockModel, MockRecord, etc.)
- `tests/conftest.py::mock_odoo_env()` - Fixture with proper typing

## Contributing Tests

When adding new features:

1. **Write tests first** (TDD approach)
2. **Cover happy path and error cases**
3. **Add integration tests for complex features**
4. **Update this documentation**
5. **Ensure tests are deterministic**
6. **Mock external dependencies**
7. **Use descriptive test names**
8. **Include docstrings for complex tests**

## Common Issues

### Docker Not Available
Some integration tests require Docker. Skip them with:
```bash
pytest -m "not docker"
```

### Slow Tests
Run fast unit tests only:
```bash
pytest tests/unit/ -m "not slow"
```

### Flaky Tests
Report flaky tests with details:
- Test name and location
- Failure frequency
- Error message
- Steps to reproduce

## Maintenance

### Regular Tasks
- Review and update mock data quarterly
- Remove obsolete tests
- Refactor duplicate test code
- Update coverage thresholds
- Profile test performance

### Test Review Checklist
- [ ] Tests are deterministic
- [ ] Mock data matches real Odoo
- [ ] Error scenarios covered
- [ ] Security implications tested
- [ ] Documentation updated
- [ ] No hardcoded values
- [ ] Proper cleanup in teardown