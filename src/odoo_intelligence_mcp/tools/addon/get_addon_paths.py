import shlex

from ...core.env import _resolve_container_env, _split_env_list, load_env_config
from ...utils.docker_utils import DockerClientManager


async def get_addon_paths_from_container(container_name: str | None = None) -> list[str]:
    config = load_env_config()
    docker_manager = DockerClientManager()

    container_candidates = [
        container_name,
        config.script_runner_container,
        config.web_container,
    ]
    selected_container = None
    for candidate in container_candidates:
        if not candidate:
            continue
        container_result = docker_manager.get_container(candidate)
        if container_result.get("success"):
            selected_container = str(container_result.get("container") or candidate)
            break

    env_paths: list[str] = []
    if selected_container:
        env_vars = _resolve_container_env(selected_container)
        for key in (
            "ODOO_ADDONS_PATH",
            "LOCAL_ADDONS_DIRS",
            "IMAGE_EXTRA_ADDONS_LOCATION",
            "IMAGE_ODOO_ENTERPRISE_LOCATION",
        ):
            raw = env_vars.get(key)
            if raw:
                env_paths.extend(_split_env_list(raw))

    if not env_paths:
        env_paths = _split_env_list(config.addons_path)

    seen: set[str] = set()
    candidates = [path for path in env_paths if not (path in seen or seen.add(path))]

    if not selected_container or not candidates:
        return candidates

    quoted = " ".join(shlex.quote(path) for path in candidates)
    check_cmd = ["sh", "-c", f"for path in {quoted}; do [ -d \"$path\" ] && echo \"$path\"; done"]
    exec_result = docker_manager.exec_run(selected_container, check_cmd)
    if not exec_result.get("success") or exec_result.get("exit_code") != 0:
        return candidates

    existing = [line.strip() for line in exec_result.get("stdout", "").splitlines() if line.strip()]
    return existing or candidates
