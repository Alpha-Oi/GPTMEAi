"""Official runtime bootstrap for the current AI OS prototype."""

from ai_os.config import get_project_paths, get_runtime_config, load_env_file


def main() -> None:
    load_env_file()
    paths = get_project_paths()
    runtime = get_runtime_config()

    print(f"[AI OS] project root: {paths.project_root}")
    print(f"[AI OS] dashboard: {paths.dashboard_file}")
    print(f"[AI OS] runtime store: {paths.runtime_file}")
    print(f"[AI OS] host={runtime.host} port={runtime.port}")

    from scripts.api_server import main as start_api_server

    start_api_server()
