"""Card files are copied off the event loop. No Home Assistant."""
from __future__ import annotations

import ast
from pathlib import Path

_INIT = Path(__file__).resolve().parents[1] / "custom_components" / "piherder" / "__init__.py"


def _copy_fn():
    tree = ast.parse(_INIT.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "copy_frontend_files":
            module = ast.Module(body=[node], type_ignores=[])
            ast.fix_missing_locations(module)
            ns: dict = {"Path": Path}
            exec(compile(module, str(_INIT), "exec"), ns)
            return ns["copy_frontend_files"]
    raise AssertionError("copy_frontend_files missing")


def test_copy_frontend_files_writes_card_and_logo(tmp_path: Path):
    www = tmp_path / "www"
    www.mkdir()
    (www / "piherder-dashboard-card.js").write_text("card-body", encoding="utf-8")
    (www / "piherder-logo.png").write_bytes(b"png")
    dest = tmp_path / "config" / "www"
    _copy_fn()(www, dest)
    assert (dest / "piherder-dashboard-card.js").read_text(encoding="utf-8") == "card-body"
    assert (dest / "piherder-logo.png").read_bytes() == b"png"


def test_copy_frontend_files_skips_missing_logo(tmp_path: Path):
    www = tmp_path / "www"
    www.mkdir()
    (www / "piherder-dashboard-card.js").write_text("card", encoding="utf-8")
    dest = tmp_path / "www-out"
    _copy_fn()(www, dest)
    assert (dest / "piherder-dashboard-card.js").is_file()
    assert not (dest / "piherder-logo.png").exists()


def test_register_frontend_runs_copy_in_an_executor():
    text = _INIT.read_text(encoding="utf-8")
    assert "await hass.async_add_executor_job(copy_frontend_files, www, dest_dir)" in text
    assert "dest_dir.mkdir" not in text.split("async def _async_register_frontend", 1)[1].split(
        "async def ", 1
    )[0]
