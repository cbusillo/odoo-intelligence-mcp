import inspect
from collections.abc import Callable
from pathlib import Path
from types import TracebackType
from typing import Any
from unittest.mock import MagicMock, patch


class MockEnv:
    """Mock environment for testing that properly handles model access and containment checks."""

    def __init__(self) -> None:
        self.models: dict[str, MagicMock] = {}

    def __contains__(self, model_name: str) -> bool:
        return model_name in self.models

    def __getitem__(self, model_name: str) -> MagicMock:
        if model_name not in self.models:
            raise KeyError(f"Model {model_name} not found")
        return self.models[model_name]

    def add_model(self, model_name: str, model: MagicMock) -> None:
        self.models[model_name] = model


def create_mock_handle_operation() -> Callable[[str, str, Callable], dict[str, Any]]:
    """Create a mock handle_container_operation function for testing Docker operations."""

    def mock_handle_operation(container_name: str, operation_name: str, operation_func: Callable) -> dict[str, Any]:
        # Get the mock container from the closure or create one
        mock_container = getattr(mock_handle_operation, "container", MagicMock())
        # Call the operation function to get the inner result
        inner_result = operation_func(mock_container)
        return {"success": True, "operation": operation_name, "container": container_name, "data": inner_result}

    return mock_handle_operation


def create_mock_user(login: str = "test_user", name: str = "Test User", groups: list[str] | None = None) -> MagicMock:
    """Create a mock Odoo user with standard properties."""
    mock_user = MagicMock()
    mock_user.login = login
    mock_user.name = name
    mock_user.groups_id = [MagicMock(name=group) for group in (groups or [])]
    return mock_user


def create_mock_model(model_name: str, **access_settings: Any) -> MagicMock:
    """Create a mock Odoo model with access control settings.

    Args:
        model_name: The model name (e.g., 'res.partner')
        **access_settings: Keyword arguments for access control:
            - check_access_rights: Return value or exception to raise
            - check_access_rule: Return value or exception to raise
            - browse_return: Mock record to return from browse()
    """
    mock_model = MagicMock()
    mock_model._name = model_name

    # Handle check_access_rights
    access_rights = access_settings.get("check_access_rights", True)
    if isinstance(access_rights, Exception):
        mock_model.check_access_rights.side_effect = access_rights
    else:
        mock_model.check_access_rights.return_value = access_rights

    # Handle check_access_rule
    access_rule = access_settings.get("check_access_rule")
    if isinstance(access_rule, Exception):
        mock_model.check_access_rule.side_effect = access_rule
    else:
        mock_model.check_access_rule.return_value = access_rule

    # Handle browse
    if "browse_return" in access_settings:
        mock_model.browse.return_value = access_settings["browse_return"]

    return mock_model


def setup_mock_odoo_env_for_permissions(mock_odoo_env: Any, users: dict[str, MagicMock], models: dict[str, MagicMock]) -> None:
    """Set up a mock Odoo environment for permission testing.

    Args:
        mock_odoo_env: The mock Odoo environment
        users: Dict of user login -> mock user objects
        models: Dict of model name -> mock model objects
    """
    # Create user model that can search for users
    mock_user_model = MagicMock()

    def search_side_effect(domain: list[Any]) -> list[MagicMock]:
        # Simple domain parsing for login searches
        for condition in domain:
            if len(condition) == 3 and condition[0] == "login" and condition[1] == "=":
                login = condition[2]
                if login in users:
                    return [users[login]]
        return []

    mock_user_model.search.side_effect = search_side_effect

    # Set up environment
    env_dict = {"res.users": mock_user_model}
    env_dict.update(models)
    mock_odoo_env.env = env_dict


class MockFileSystemContext:
    def __init__(self, mock_files: list[Path], mock_file_contents: dict[Path, str]) -> None:
        self.mock_files = mock_files
        self.mock_file_contents = mock_file_contents
        self._patches = []

    def __enter__(self) -> "MockFileSystemContext":
        # Patch Path.glob
        self.mock_glob = patch("pathlib.Path.glob")
        glob_patch = self.mock_glob.__enter__()
        glob_patch.return_value = self.mock_files
        self._patches.append(self.mock_glob)

        # Patch Path.open
        def open_side_effect(path_self: Any, *_args: Any, **_kwargs: Any) -> Any:
            mock_file = MagicMock()
            content = self.mock_file_contents.get(path_self, "")
            mock_file.__enter__.return_value.read.return_value = content
            return mock_file

        self.mock_open = patch("pathlib.Path.open", side_effect=open_side_effect)
        self.mock_open.__enter__()
        self._patches.append(self.mock_open)

        # Patch Path.is_file
        self.mock_is_file = patch("pathlib.Path.is_file", return_value=True)
        self.mock_is_file.__enter__()
        self._patches.append(self.mock_is_file)

        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> None:
        for patch_obj in reversed(self._patches):
            patch_obj.__exit__(exc_type, exc_val, exc_tb)


def mock_file_system(mock_files: list[Path], mock_file_contents: dict[Path, str]) -> MockFileSystemContext:
    return MockFileSystemContext(mock_files, mock_file_contents)


def create_mock_env_with_fields(model_fields: dict[str, dict[str, Any]]) -> MagicMock:
    mock_env = MagicMock()

    # Create all models first
    models = {}
    for model_name, fields in model_fields.items():
        mock_model = MagicMock()
        mock_model._fields = fields
        models[model_name] = mock_model

    # Set up the getter to return appropriate model
    def get_model(name: str) -> MagicMock:
        return models.get(name, MagicMock())

    mock_env.__getitem__.side_effect = get_model

    return mock_env


def create_exists_side_effect_for_module_structure(module_name: str, has_static: bool = True) -> Callable[[], bool]:
    def exists_side_effect() -> Any:
        # Use call stack inspection to determine what's calling
        frame = inspect.currentframe().f_back
        if frame and frame.f_locals:
            local_vars = frame.f_locals
            # Check if this is checking static_path
            if "static_path" in local_vars:
                return has_static
            # Check if this is the initial module check
            if "module_path" in local_vars and str(local_vars["module_path"]) == module_name:
                return False  # Bare module name doesn't exist
        return True  # Everything else exists

    return exists_side_effect


def create_mock_record(exists: bool = True, **attributes: Any) -> MagicMock:
    """Create a mock Odoo record with standard properties."""
    mock_record = MagicMock()
    mock_record.exists.return_value = exists

    # Set any additional attributes
    for key, value in attributes.items():
        setattr(mock_record, key, value)

    return mock_record
