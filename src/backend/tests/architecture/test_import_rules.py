"""Kiểm tự động quy tắc phụ thuộc backend (docs/prd/architecture.md §2, quy tắc 1–9 và 11).

Quét AST mọi file trong `src/backend/app`, kể cả import nằm trong thân hàm, nên import "lười" cũng bị bắt.
Chỉ dùng stdlib để không thêm dependency. Thêm ngoại lệ ở đây nghĩa là đổi quy tắc kiến trúc:
phải có đề xuất đã chốt trong `docs/prd/update/` trước (AGENTS.md §8).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "app"
PACKAGE = "src.backend.app"
LAYERS = ("domain", "application", "infrastructure", "agents", "api", "core", "main")

# Lớp trong app mà mỗi lớp KHÔNG được import.
FORBIDDEN_LAYERS: dict[str, set[str]] = {
    "domain": {"application", "infrastructure", "agents", "api", "core", "main"},  # quy tắc 1, 4
    "application": {"infrastructure", "agents", "api", "main"},  # quy tắc 1, 2, 5
    "core": {"domain", "application", "infrastructure", "agents", "api", "main"},  # core là nền, không phụ thuộc ai
    "agents": {"infrastructure", "api", "main"},  # quy tắc 7
    "api": {"infrastructure", "agents", "main"},  # quy tắc 6, 8
    "infrastructure": {"agents", "api", "main"},
}

_WEB = {"fastapi", "starlette"}
_DB = {"psycopg", "psycopg2", "psycopg_pool", "sqlalchemy", "sqlite3", "weaviate"}
_HTTP = {"httpx", "requests"}
_LLM_SDK = {"openai", "anthropic", "cohere", "langchain_openai", "langchain_anthropic", "langchain_google_genai",
            "google"}
_AGENT_FRAMEWORK = {"langgraph", "langchain", "langchain_core"}

# Thư viện bên ngoài mà mỗi lớp KHÔNG được import (so theo tên module gốc).
FORBIDDEN_LIBRARIES: dict[str, set[str]] = {
    "domain": _WEB | _DB | _HTTP | _LLM_SDK | _AGENT_FRAMEWORK | {"pydantic", "pydantic_settings"},  # quy tắc 4
    "application": _WEB | _DB | _HTTP | _LLM_SDK | _AGENT_FRAMEWORK,  # quy tắc 2
    "core": _WEB,  # quy tắc 9
    "agents": _WEB | _DB | _HTTP | _LLM_SDK,  # quy tắc 7: dùng port, không tự gọi DB/HTTP/SDK
    "api": _DB | _LLM_SDK | _AGENT_FRAMEWORK,  # quy tắc 6
}


def _module_name(path: Path, root: Path) -> str:
    return ".".join((PACKAGE, *path.relative_to(root).with_suffix("").parts)).removesuffix(".__init__")


def _layer(path: Path, root: Path = APP) -> str:
    first = path.relative_to(root).parts[0]
    return first.removesuffix(".py") if first.removesuffix(".py") in LAYERS else ""


def _imports(path: Path, root: Path) -> list[tuple[int, str]]:
    """(dòng, tên module tuyệt đối) cho mọi import trong file; import tương đối được quy về tuyệt đối."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module = _module_name(path, root)
    package = module if path.name == "__init__.py" else module.rsplit(".", 1)[0]
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                base = base[: len(base) - node.level + 1]
                name = ".".join(base + ([node.module] if node.module else []))
            else:
                name = node.module or ""
            found.append((node.lineno, name))
    return found


def _violations(layer: str, root: Path = APP) -> list[str]:
    errors = []
    for path in sorted(root.rglob("*.py")):
        if _layer(path, root) != layer:
            continue
        for line, name in _imports(path, root):
            where = f"{path.relative_to(root)}:{line} import {name}"
            if name.startswith(PACKAGE + "."):
                target = name.removeprefix(PACKAGE + ".").split(".")[0]
                if target in FORBIDDEN_LAYERS.get(layer, set()):
                    errors.append(f"{where} — lớp `{layer}` không được phụ thuộc `{target}`")
            elif name.split(".")[0] in FORBIDDEN_LIBRARIES.get(layer, set()):
                errors.append(f"{where} — lớp `{layer}` không được import `{name.split('.')[0]}`")
    return errors


@pytest.mark.parametrize("layer", sorted(set(FORBIDDEN_LAYERS) | set(FORBIDDEN_LIBRARIES)))
def test_layer_respects_dependency_rules(layer: str) -> None:
    assert _violations(layer) == []


def test_every_module_belongs_to_a_known_layer() -> None:
    """File mới ngoài các lớp đã biết sẽ lọt khỏi mọi quy tắc trên."""
    strays = [str(p.relative_to(APP)) for p in APP.rglob("*.py") if p.name != "__init__.py" and not _layer(p)]
    assert strays == []


def test_the_scanner_catches_a_violation(tmp_path: Path) -> None:
    """Test âm: không có ca này thì một lỗi quét (đường dẫn sai, bỏ sót import tương đối) cũng cho kết quả xanh."""
    assert any(_layer(p) == "domain" for p in APP.rglob("*.py"))
    (tmp_path / "domain" / "search").mkdir(parents=True)
    (tmp_path / "domain" / "search" / "bad.py").write_text(
        "import fastapi\n"
        "def lazy():\n    from ...infrastructure.cdp import local_cdp_client\n",
        encoding="utf-8",
    )
    errors = _violations("domain", tmp_path)
    assert len(errors) == 2
    assert "import fastapi" in errors[0]
    assert "src.backend.app.infrastructure.cdp" in errors[1]
