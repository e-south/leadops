from pathlib import Path

from crm.config import WORKSPACES_DIR, _resolve_sqlite_path


def test_resolve_sqlite_path_relative(tmp_path: Path) -> None:
    ws_dir = tmp_path / WORKSPACES_DIR / "demo"
    ws_dir.mkdir(parents=True)
    config_path = ws_dir / "workspace.yaml"
    config_path.write_text("workspace: demo\nstore:\n  sqlite_path: ./local.sqlite\n")

    resolved = _resolve_sqlite_path("./local.sqlite", config_path)
    assert resolved == (ws_dir / "local.sqlite").resolve()


def test_resolve_sqlite_path_repo_relative(tmp_path: Path) -> None:
    ws_dir = tmp_path / WORKSPACES_DIR / "demo"
    ws_dir.mkdir(parents=True)
    config_path = ws_dir / "workspace.yaml"
    config_path.write_text("workspace: demo\nstore:\n  sqlite_path: workspaces/demo/local.sqlite\n")

    resolved = _resolve_sqlite_path("workspaces/demo/local.sqlite", config_path)
    assert resolved == (tmp_path / "workspaces" / "demo" / "local.sqlite").resolve()
