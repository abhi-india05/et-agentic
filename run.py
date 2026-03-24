"""
Project runner for RevOps AI (backend + frontend).

Usage:
  python run.py                 # starts backend + frontend
  python run.py backend         # backend only
  python run.py frontend        # frontend only
  python run.py all --install   # install deps, then start both

Notes:
  - Backend runs on http://localhost:8000 (FastAPI / Uvicorn)
  - Frontend runs on http://localhost:5173 (Vite dev server)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"


def _die(msg: str, code: int = 2) -> "NoReturn":
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _which(exe: str) -> str | None:
    return shutil.which(exe)


def _run(cmd: list[str], *, cwd: Path, check: bool = True) -> int:
    # Inherit the user's shell environment; keep output streaming.
    proc = subprocess.run(cmd, cwd=str(cwd), check=False)
    if check and proc.returncode != 0:
        _die(f"command failed ({proc.returncode}): {' '.join(cmd)}", code=proc.returncode)
    return proc.returncode


def _popen(cmd: list[str], *, cwd: Path) -> subprocess.Popen:
    # On Windows, popping each server in its own console is convenient.
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    return subprocess.Popen(cmd, cwd=str(cwd), creationflags=creationflags)


def install_backend() -> None:
    req = BACKEND_DIR / "requirements.txt"
    if not req.exists():
        _die(f"missing backend requirements: {req}")
    _run([sys.executable, "-m", "pip", "install", "-r", str(req)], cwd=REPO_ROOT)


def install_frontend() -> None:
    if not FRONTEND_DIR.exists():
        _die(f"missing frontend directory: {FRONTEND_DIR}")
    npm = _which("npm")
    if not npm:
        _die("npm not found on PATH. Install Node.js, then re-run with --install.")
    _run([npm, "install"], cwd=FRONTEND_DIR)


def start_backend(*, host: str, port: int, reload: bool) -> subprocess.Popen:
    # Ensure uvicorn is importable; if not, guide the user.
    try:
        import uvicorn  # noqa: F401
    except Exception:
        _die("backend deps not installed. Run: python run.py backend --install")

    app = "backend.main:app"
    cmd = [sys.executable, "-m", "uvicorn", app, "--host", host, "--port", str(port)]
    if reload:
        cmd.append("--reload")
    return _popen(cmd, cwd=REPO_ROOT)


def start_frontend() -> subprocess.Popen:
    npm = _which("npm")
    if not npm:
        _die("npm not found on PATH. Install Node.js, then run: python run.py frontend --install")
    return _popen([npm, "run", "dev"], cwd=FRONTEND_DIR)


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run the RevOps AI backend/frontend.")
    p.add_argument(
        "target",
        nargs="?",
        default="all",
        choices=["all", "backend", "frontend"],
        help="what to run (default: all)",
    )
    p.add_argument(
        "--install",
        action="store_true",
        help="install dependencies before starting (pip + npm)",
    )
    p.add_argument("--host", default="127.0.0.1", help="backend host (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=8000, help="backend port (default: 8000)")
    p.add_argument(
        "--no-reload",
        action="store_true",
        help="disable backend autoreload (default: enabled)",
    )
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    if not BACKEND_DIR.exists():
        _die(f"missing backend directory: {BACKEND_DIR}")
    if not FRONTEND_DIR.exists():
        _die(f"missing frontend directory: {FRONTEND_DIR}")

    reload = not args.no_reload

    if args.install:
        if args.target in ("all", "backend"):
            install_backend()
        if args.target in ("all", "frontend"):
            install_frontend()

    procs: list[subprocess.Popen] = []
    if args.target in ("all", "backend"):
        procs.append(start_backend(host=args.host, port=args.port, reload=reload))
        print(f"backend: http://{args.host}:{args.port}")
        print(f"backend: http://{args.host}:{args.port}/docs")

    if args.target in ("all", "frontend"):
        procs.append(start_frontend())
        print("frontend: http://localhost:5173")

    if not procs:
        _die("nothing to run")

    print("Press Ctrl+C to stop.")
    try:
        # Keep this parent process alive while children run.
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            if p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

