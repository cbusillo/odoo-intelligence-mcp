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

```python
from tests.fixtures import assert_handles_docker_failure

async def test_tool_with_docker_failure() -> None:
    await assert_handles_docker_failure(
        tool_function,
        required_arg="value"
    )
```

### Testing Error Scenarios

```python
async def test_handles_model_not_found() -> None:
    mock_env = AsyncMock()
    mock_env.execute_code = AsyncMock(
        side_effect=ModelNotFoundError("Model not found")
    )
    
    result = await tool_function(mock_env, "invalid.model")
    assert "error" in result
    assert result["error_type"] == "ModelNotFoundError"
```

### Testing Pagination

```python
from tests.fixtures import assert_paginated_response

async def test_paginated_response() -> None:
    result = await tool_function(env, pattern="test", page=2, page_size=10)
    assert_paginated_response(result)
    assert result["pagination"]["page"] == 2
```

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
```python
async def test_example() -> None:
    # Arrange
    mock_env = create_mock_environment()
    
    # Act
    result = await function_under_test(mock_env)
    
    # Assert
    assert result["success"] is True
```

### 3. Comprehensive Assertions
```python
# Don't just check for existence
assert "field" in result  # Basic

# Verify structure and content
assert_model_info_response(result, "res.partner")  # Comprehensive
```

### 4. Error Message Testing
```python
# Verify error messages are helpful
assert "error" in result
assert "Model test.model not found" in result["error"]  # Specific
assert result["error_type"] == "ModelNotFoundError"
```

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
```python
from tests.fixtures import (
    assert_error_response,
    assert_model_info_response,
    assert_paginated_response,
    assert_tool_response_valid,
    create_field_info,
    create_mock_odoo_model,
    create_mock_registry,
    create_odoo_response,
)

# Use in your tests
async def test_model_with_error() -> None:
    result = await get_model_info(mock_env, "invalid.model")
    assert_error_response(result, "Model invalid.model not found")
```

### Docker Testing Helpers
```python
from tests.fixtures import (
    create_docker_manager_with_get_container,
    create_successful_container_mock,
    get_expected_container_names,
    get_test_config,
    setup_docker_manager_mock,
)

# Test Docker container operations
async def test_container_operation() -> None:
    config = get_test_config()
    container_names = get_expected_container_names()
    mock_container = create_successful_container_mock()
    # ... test implementation
```

### Mock Utilities
```python
from tests.fixtures import (
    MockEnv,
    create_mock_env_with_fields,
    create_mock_model,
    create_mock_record,
    create_mock_user,
)

# Create mock environment with specific fields
def test_with_mock_env() -> None:
    fields = {"name": {"type": "char"}, "email": {"type": "char"}}
    mock_env = create_mock_env_with_fields("res.partner", fields)
    # ... test implementation
```

### Type Definitions
```python
from tests.fixtures import (
    MockOdooEnvironment,
    MockModel,
    MockRecord,
    MockRecordset,
    MockRegistry,
)

# Use proper type hints in tests
async def test_with_types(mock_env: MockOdooEnvironment) -> None:
    model: MockModel = mock_env["res.partner"]
    record: MockRecord = model.browse(1)
    # ... test implementation
```

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