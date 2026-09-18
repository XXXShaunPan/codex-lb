"""Fail CI if the maintained relay accidentally regains startup monkey patches."""

from __future__ import annotations

import ast
from pathlib import Path

from alembic.script import ScriptDirectory

from app.db.migrate import _build_alembic_config


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = []
    for feature in ("virtual_accounts", "provider_billing", "visitor_access", "codex_config", "provider_compatibility"):
        for path in (root / "app/modules" / feature).glob("*.py"):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "setattr":
                    errors.append(f"{path.relative_to(root)}:{node.lineno}: runtime attribute replacement")
                if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("codex_lb_"):
                    errors.append(f"{path.relative_to(root)}:{node.lineno}: external injection import")
            if "sitecustomize" in source or "__codex_lb_injection" in source:
                errors.append(f"{path.relative_to(root)}: external startup/HTML injection dependency")
    config = _build_alembic_config("sqlite:///relay-policy-check.db")
    heads = ScriptDirectory.from_config(config).get_heads()
    if len(heads) != 1:
        errors.append(f"Expected one Alembic head, found {heads}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"native_relay=ok alembic_head={heads[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
