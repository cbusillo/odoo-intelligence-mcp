# Common test helpers
from .common import (
    assert_model_info_response,
)

# Docker helpers
from .docker import (
    create_docker_manager_with_get_container,
    create_successful_container_mock,
    get_expected_container_names,
    get_test_config,
)

# Odoo fixtures - these are pytest fixtures, need special handling
from .odoo import (
    MockDockerRun,
    docker_available,
    mock_docker_run,
    mock_res_partner_data,
    real_odoo_env_if_available,
)

# Type definitions
from .types import (
    ConcreteModelMock,
    MockCompletedProcess,
    MockCursor,
    MockEnvFixture,
    MockField,
    MockFieldFixture,
    MockModel,
    MockOdooEnvironment,
    MockOdooModel,
    MockRecord,
    MockRecordset,
    MockRegistry,
    MockRegistryFixture,
    MockSubprocessRun,
)

__all__ = [
    # Type definitions
    "ConcreteModelMock",
    "MockCompletedProcess",
    "MockCursor",
    # Odoo fixtures
    "MockDockerRun",
    "MockEnvFixture",
    "MockField",
    "MockFieldFixture",
    "MockModel",
    "MockOdooEnvironment",
    "MockOdooModel",
    "MockRecord",
    "MockRecordset",
    "MockRegistry",
    "MockRegistryFixture",
    "MockSubprocessRun",
    # Common helpers
    "assert_model_info_response",
    # Docker helpers
    "create_docker_manager_with_get_container",
    "create_successful_container_mock",
    "docker_available",
    "get_expected_container_names",
    "get_test_config",
    "mock_docker_run",
    "mock_res_partner_data",
    "real_odoo_env_if_available",
]
