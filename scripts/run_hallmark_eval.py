#!/usr/bin/env python3
"""Launcher for HALLMARK eval (requires Python 3.10+ and HALLMARK on PYTHONPATH)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pick_python() -> str:
    eval_venv = ROOT / ".venv-eval" / "bin" / "python"
    if eval_venv.is_file():
        return str(eval_venv)
    for name in ("python3.12", "python3.11", "python3.10"):
        path = shutil.which(name)
        if path:
            return path
    ver = sys.version_info
    if ver >= (3, 10):
        return sys.executable
    print(
        "HALLMARK evaluation requires Python 3.10+.\n"
        "Install python3.11, then: bash scripts/install_hallmark.sh",
        file=sys.stderr,
    )
    raise SystemExit(1)


def main() -> None:
    hallmark_root = Path(os.environ.get("HALLMARK_ROOT", ROOT / ".vendor" / "hallmark"))
    if not (hallmark_root / "hallmark").is_dir():
        print(
            f"HALLMARK not found at {hallmark_root}\n"
            "Run: bash scripts/install_hallmark.sh  # also creates .venv-eval",
            file=sys.stderr,
        )
        raise SystemExit(1)

    py = _pick_python()
    env = os.environ.copy()
    paths = [str(ROOT), str(hallmark_root)]
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    env.setdefault("HALLMARK_ROOT", str(hallmark_root))

    cmd = [py, "-m", "eval.citebench.run_eval", *sys.argv[1:]]
    raise SystemExit(subprocess.call(cmd, env=env, cwd=str(ROOT)))


if __name__ == "__main__":
    main()
