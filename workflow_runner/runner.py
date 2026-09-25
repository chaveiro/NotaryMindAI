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

from workflow_runner.common import RunnerError, build_runtime_config, build_run_summary, selected_model
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
    args = sys.argv[1:]
    if len(args) < 2:
        print("Usage: runner.py <ocr|interpret|map> <project_path> [--only-new] [model]", file=sys.stderr)
        return 2

    operation = args[0]
    raw_project = args[1]
    only_new = False
    cli_model = ""
    for token in args[2:]:
        if token == "--only-new":
            only_new = True
        elif token.startswith("-"):
            print(f"Unsupported flag: {token}", file=sys.stderr)
            return 2
        elif not cli_model:
            cli_model = token
        else:
            print(f"Unexpected argument: {token}", file=sys.stderr)
            return 2

    if operation not in OPERATIONS:
        print(f"Unsupported operation: {operation}", file=sys.stderr)
        return 2
    model = selected_model(operation, cli_model)
    try:
        project = _project_path(raw_project)
        with ProjectLock(project):
            if operation == "ocr":
                summary = run_ocr(project, model, only_new=only_new)
            elif operation == "interpret":
                summary = run_interpret(project, model, only_new=only_new)
            else:
                summary = run_map(project, model, only_new=only_new)
        summary = build_run_summary(
            operation,
            model=model,
            processed=int(summary.get("processed", 0)),
            failed=summary.get("failed", []),
            files_written=summary.get("files_written", []),
            skipped=summary.get("skipped"),
            documents=summary.get("documents"),
            images_mapped=summary.get("images_mapped"),
            status=(summary.get("status") or ("error" if summary.get("failed") else "ok")),
            **{k: v for k, v in summary.items() if k not in {"operation", "model", "status", "processed", "failed", "files_written", "skipped", "documents", "images_mapped"}},
        )
        print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
        return 1 if summary.get("failed") else 0
    except RunnerError as error:
        message = str(error)
        hint = message if "Please visit" in message or "GitHub Copilot" in message else ""
        summary = build_run_summary(
            operation,
            model=model,
            status="error",
            processed=0,
            failed=[message],
            files_written=[],
        )
        print(json.dumps(summary, ensure_ascii=False), file=sys.stderr)
        return 1
    except Exception as error:
        summary = build_run_summary(
            operation,
            model=model,
            status="error",
            processed=0,
            failed=[f"unexpected runner error: {error}"],
            files_written=[],
        )
        print(json.dumps(summary, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
