"""Record the source tree and hashes of an already verified production build."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    static = root / "app/static"
    if not (static / "index.html").is_file():
        raise SystemExit("Build the frontend first")
    if subprocess.check_output(["git", "status", "--porcelain", "--", "frontend"], cwd=root).strip():
        raise SystemExit("Commit the frontend source before stamping its build")
    tree = subprocess.check_output(["git", "rev-parse", "HEAD:frontend"], cwd=root, text=True).strip()
    files = [
        {"path": path.relative_to(static).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in sorted(static.rglob("*"))
        if path.is_file() and path.name != "relay-build.json"
    ]
    (static / "relay-build.json").write_text(
        json.dumps({"frontendTree": tree, "files": files}, indent=2), encoding="utf-8"
    )
    print(f"frontend_tree={tree} verified_files={len(files)}")


if __name__ == "__main__":
    main()
