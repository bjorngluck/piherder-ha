"""The card is served from the integration folder. No Home Assistant."""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_INIT = _ROOT / "custom_components" / "piherder" / "__init__.py"
_CARD = _ROOT / "custom_components" / "piherder" / "www" / "piherder-dashboard-card.js"
_MANIFEST = _ROOT / "custom_components" / "piherder" / "manifest.json"
_HACS = _ROOT / "hacs.json"
_URL = "/piherder/piherder-dashboard-card.js?v=0.5.2"


def _action():
    tree = ast.parse(_INIT.read_text(encoding="utf-8"))
    body = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "_LEGACY_CARD_STEMS"
            for target in node.targets
        ):
            body.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name == "card_resource_action":
            body.append(node)
    if len(body) != 2:
        raise AssertionError("card_resource_action missing")
    module = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(module)
    ns: dict = {}
    exec(compile(module, str(_INIT), "exec"), ns)
    return ns["card_resource_action"]


def test_new_url_is_kept():
    action = _action()
    decision, item = action([{"id": "a", "url": _URL}], _URL)
    assert decision == "keep"
    assert item is None


def test_local_resource_is_updated_in_place():
    action = _action()
    old = {"id": "a", "url": "/local/piherder-dashboard-card.js?v=0.5.1"}
    decision, item = action([old], _URL)
    assert decision == "update"
    assert item is old


def test_api_resource_is_updated_in_place():
    action = _action()
    old = {"id": "b", "url": "/api/piherder/piherder-dashboard-card.js"}
    decision, item = action([{"url": "/other.js"}, old], _URL)
    assert decision == "update"
    assert item is old


def test_missing_resource_is_created():
    action = _action()
    decision, item = action([{"id": "z", "url": "/other.js"}], _URL)
    assert decision == "create"
    assert item is None


def test_current_url_wins_over_a_leftover_local_resource():
    action = _action()
    decision, item = action(
        [
            {"id": "old", "url": "/local/piherder-dashboard-card.js?v=0.5.1"},
            {"id": "new", "url": _URL},
        ],
        _URL,
    )
    assert decision == "keep"
    assert item is None


def test_register_frontend_serves_the_integration_folder():
    text = _INIT.read_text(encoding="utf-8")
    register = text.split("async def _async_register_frontend", 1)[1].split(
        "async def ", 1
    )[0]
    assert (
        'StaticPathConfig("/piherder", str(Path(__file__).parent / "www"), True)'
        in register
    )
    assert "async_register_static_paths" in register
    assert "frontend.add_extra_js_url" in register
    assert "copy_frontend_files" not in text
    assert "PiHerderCardView" not in text
    assert "frontend_extra_module_url" not in text
    assert 'config.path("www")' not in text
    assert "/local/piherder-logo.png" not in _CARD.read_text(encoding="utf-8")
    assert "/piherder/piherder-logo.png" in _CARD.read_text(encoding="utf-8")
    assert '"version": "0.5.2"' in _MANIFEST.read_text(encoding="utf-8")
    assert '"frontend"' in _MANIFEST.read_text(encoding="utf-8")
    assert '"homeassistant": "2024.7.0"' in _HACS.read_text(encoding="utf-8")
