#!/usr/bin/env python3
"""Run the named GenAI operations used by the NotaryMindAI API.

CLI contract: runner.py <operation> <project_path> [model]
Operations: ocr, interpret, map
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from workflow_runner.common import RunnerError, build_runtime_config, selected_model
from workflow_runner.tasks.ocr_task import run_ocr
from workflow_runner.tasks.interpret_task import run_interpret
from workflow_runner.tasks.map_task import run_map

OPERATIONS = {"ocr", "interpret", "map"}


class ProjectLock:
    def __init__(self, project: Path):
        self.project = project.resolve()
        project_id = hashlib.sha1(str(self.project).encode("utf-8")).hexdigest()[:12]
        self.path = Path(tempfile.gettempdir()) / f"notarymindai-workflow-{self.project.name}-{project_id}.lock"

    def _write_owner(self) -> None:
        self.path.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")

    def _is_running(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def _stale(self) -> bool:
        if not self.path.exists():
            return True
        try:
            owner = json.loads(self.path.read_text(encoding="utf-8"))
            pid = int(owner.get("pid", 0))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return True
        if pid <= 0:
            return True
        return not self._is_running(pid)

    def _clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def __enter__(self):
        try:
            lock_fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(lock_fd)
        except FileExistsError as error:
            if not self._stale():
                raise RunnerError(
                    f"Project '{self.project.name}' is already being processed. "
                    f"Project path: {self.project}. Temporary lock file: {self.path}"
                ) from error
            self._clear()
            try:
                lock_fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(lock_fd)
            except FileExistsError as retry_error:
                raise RunnerError(
                    f"Project '{self.project.name}' is already being processed. "
                    f"Project path: {self.project}. Temporary lock file: {self.path}"
                ) from retry_error
        self._write_owner()
        return self

    def __exit__(self, *_args):
        self._clear()


def _project_path(raw: str) -> Path:
    project = Path(raw).expanduser().resolve()
    if not project.is_dir() or not (project / "imported").is_dir():
        raise RunnerError(f"Invalid project directory: {project}")
    return project


def main() -> int:
    if len(sys.argv) not in (3, 4):
        print("Usage: runner.py <ocr|interpret|map> <project_path> [model]", file=sys.stderr)
        return 2
    operation, raw_project = sys.argv[1:3]
    cli_model = sys.argv[3] if len(sys.argv) == 4 else ""
    if operation not in OPERATIONS:
        print(f"Unsupported operation: {operation}", file=sys.stderr)
        return 2
    model = selected_model(operation, cli_model)
    try:
        project = _project_path(raw_project)
        with ProjectLock(project):
            if operation == "ocr":
                summary = run_ocr(project, model)
            elif operation == "interpret":
                summary = run_interpret(project, model)
            else:
                summary = run_map(project, model)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1 if summary.get("failed") else 0
    except RunnerError as error:
        message = str(error)
        hint = message if "Please visit" in message or "GitHub Copilot" in message else ""
        print(
            json.dumps({"ok": False, "operation": operation, "error": message, "hint": hint}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1
    except Exception as error:
        print(
            json.dumps({"ok": False, "operation": operation, "error": f"unexpected runner error: {error}", "hint": ""}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
