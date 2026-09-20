#!/usr/bin/env python3
"""Run the named GenAI operations used by the NotaryMindAI API.

CLI contract: runner.py <operation> <project_path> [model]
Operations: ocr, reinterpret, map
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import litellm  # type: ignore

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
OPERATIONS = {"ocr", "reinterpret", "map"}
COPILOT_API_BASE = "https://api.githubcopilot.com"
DEFAULT_OPENAI_BASE = "https://api.openai.com"
DEFAULT_ANTHROPIC_BASE = "https://api.anthropic.com"
DEFAULT_MODEL = "claude-opus-4.8"

MODEL_ALIASES = {
    "claude-opus-4.8": "anthropic/claude-opus-4-1-20250805",
    "claude-opus-4.1": "anthropic/claude-opus-4-1-20250805",
    "haiku-4.5": "anthropic/claude-3-5-haiku-latest",
    "copilot-gpt-4.1": "openai/gpt-4.1",
    "copilot-gpt-4o": "openai/gpt-4o",
    "gpt-4.1": "openai/gpt-4.1",
    "gpt-4o": "openai/gpt-4o",
}


class RunnerError(RuntimeError):
    """A user-actionable workflow failure."""


class ProjectLock:
    def __init__(self, project: Path):
        self.path = project / ".workflow_runner.lock"

    def __enter__(self):
        try:
            self.path.mkdir()
        except FileExistsError as error:
            raise RunnerError(f"Project is already being processed: {self.path.parent.name}") from error
        return self

    def __exit__(self, *_args):
        try:
            self.path.rmdir()
        except OSError:
            pass


def env_name(operation: str) -> str:
    return os.environ.get(f"NOTARYMIND_{operation.upper()}_MODEL", "").strip()


def selected_model(operation: str, cli_model: str) -> str:
    return env_name(operation) or os.environ.get("NOTARYMIND_GENAI_MODEL", "").strip() or cli_model or DEFAULT_MODEL


def normalize_model_name(model: str) -> str:
    raw = (model or "").strip()
    if not raw:
        return raw
    raw = raw.strip().lower().replace("_", "-").replace(" ", "-")
    if raw.startswith("/"):
        raw = raw[1:]
    if "/" in raw:
        return raw
    alias = MODEL_ALIASES.get(raw, raw)
    if alias.startswith("anthropic/") or alias.startswith("openai/") or alias.startswith("deepseek/"):
        return alias
    if raw.startswith("claude"):
        return f"anthropic/{raw}"
    if raw.startswith("copilot"):
        return f"openai/{raw.replace('copilot-', '')}"
    if raw.startswith("deepseek"):
        return f"deepseek/{raw}"
    return f"openai/{raw}"


def build_runtime_config(model: str) -> dict[str, Any]:
    normalized = normalize_model_name(model)
    provider_hint = os.environ.get("GENAI_PROVIDER", "openai").strip().lower()

    if normalized.startswith("anthropic/"):
        provider = "anthropic"
        api_key_name = "ANTHROPIC_API_KEY"
        api_base = os.environ.get("ANTHROPIC_API_BASE", os.environ.get("ANTHROPIC_BASE_URL", DEFAULT_ANTHROPIC_BASE)).rstrip("/")
    elif provider_hint in {"copilot", "githubcopilot"} or normalized.startswith(("copilot/", "github-copilot/")):
        provider = "copilot"
        api_key_name = "OPENAI_API_KEY"
        api_base = os.environ.get("OPENAI_API_BASE", os.environ.get("OPENAI_BASE_URL", COPILOT_API_BASE)).rstrip("/")
    elif provider_hint in {"lmstudio", "local"}:
        provider = "openai"
        api_key_name = "OPENAI_API_KEY"
        api_base = os.environ.get("OPENAI_API_BASE", os.environ.get("OPENAI_BASE_URL", "http://localhost:1234/v1")).rstrip("/")
    else:
        provider = "openai"
        api_key_name = "OPENAI_API_KEY"
        api_base = os.environ.get("OPENAI_API_BASE", os.environ.get("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE)).rstrip("/")

    if provider == "openai" and not normalized.startswith(("openai/", "deepseek/", "gemini/", "xai/")):
        normalized = f"openai/{normalized.split('/', 1)[-1]}"

    return {
        "provider": provider,
        "model": normalized,
        "api_key_name": api_key_name,
        "api_key": os.environ.get(api_key_name, "").strip(),
        "api_base": api_base,
    }


def _json_from_text(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2:
            cleaned = "\n".join(lines[1:-1]).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = min((i for i in (cleaned.find("{"), cleaned.find("[")) if i >= 0), default=-1)
        if start < 0:
            raise RunnerError("Provider returned no JSON object")
        try:
            return json.JSONDecoder().raw_decode(cleaned[start:])[0]
        except json.JSONDecodeError as error:
            raise RunnerError(f"Provider returned invalid JSON: {error.msg}") from error


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise RunnerError(f"Could not read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise RunnerError(f"Expected an object in {path}")
    return value


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _common_rules() -> str:
    return (
        "Use only evidence in the supplied image, transcript, glossary, or project files. "
        "Never invent names, dates, values, or relations. Use empty values or '[?]' "
        "when evidence is unavailable. Return JSON only, without Markdown."
    )


def _schema_prompt() -> str:
    return """Return an object with these keys:
{
  "image": string,
  "document_type": string,
  "document_date": string or array,
  "location": string or array,
  "full_transcript": string,
  "entities": {"names": [], "dates": [], "places": [], "values": []},
  "properties": [],
  "persons": [],
  "relations": [],
  "ocr_metadata": {"status": string, "notes": string}
}
Each relation must contain from, relation, and to. Include sellers, buyers, creditors,
and debtors in persons and relations when supported by evidence."""


def _litellm_payload(messages: list[dict[str, Any]], image: Path | None = None, provider: str | None = None) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if role == "user" and image:
            encoded = base64.b64encode(image.read_bytes()).decode("ascii")
            media_type = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
            if provider == "anthropic":
                payload.append(
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": encoded}},
                            {"type": "text", "text": str(content)},
                        ],
                    }
                )
            else:
                payload.append(
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": str(content)},
                            {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{encoded}"}},
                        ],
                    }
                )
        else:
            payload.append({"role": role, "content": str(content)})
    return payload


def _extract_text(response: Any) -> str:
    if hasattr(response, "choices"):
        choice = response.choices[0]
        message = getattr(choice, "message", None)
        text = getattr(message, "content", "")
        if isinstance(text, list):
            text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
        return str(text)
    if isinstance(response, dict):
        if isinstance(response.get("content"), list):
            return "".join(block.get("text", "") for block in response["content"] if isinstance(block, dict))
        if isinstance(response.get("choices"), list):
            return str(response["choices"][0]["message"]["content"])
        if isinstance(response.get("output_text"), str):
            return response["output_text"]
    raise RunnerError("Provider response did not contain message content")


def _request_json(messages: list[dict[str, Any]], model: str, image: Path | None = None) -> Any:
    config = build_runtime_config(model)
    provider = config["provider"]

    if not config["api_key"]:
        raise RunnerError(f"{config['api_key_name']} is not configured")

    try:
        response = litellm.completion(
            model=config["model"],
            messages=_litellm_payload(messages, image, provider),
            api_key=config["api_key"],
            api_base=config["api_base"],
            temperature=0,
            max_tokens=int(os.environ.get("GENAI_MAX_TOKENS", "12000")),
            response_format={"type": "json_object"} if provider != "anthropic" else None,
        )
        return _json_from_text(_extract_text(response))
    except Exception as error:  # pragma: no cover
        raise RunnerError(f"{provider} request failed: {error}") from error


def _project_path(raw: str) -> Path:
    project = Path(raw).expanduser().resolve()
    if not project.is_dir() or not (project / "imported").is_dir():
        raise RunnerError(f"Invalid project directory: {project}")
    return project


def _glossary(project: Path) -> str:
    path = project / "GLOSSARIO.md"
    return path.read_text(encoding="utf-8") if path.exists() else "(no glossary)"


def _metadata_files(project: Path) -> list[Path]:
    return sorted((project / "metadata").glob("*.json"))


def _run_ocr(project: Path, model: str) -> dict[str, Any]:
    imported = sorted(p for p in (project / "imported").iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS)
    metadata = project / "metadata"
    metadata.mkdir(exist_ok=True)
    pending = [image for image in imported if not (metadata / f"{image.stem}.json").exists()]
    written = []
    failures = []
    for image in pending:
        try:
            prompt = f"{_common_rules()}\n{_schema_prompt()}\nGlossary:\n{_glossary(project)}"
            result = _request_json([{"role": "user", "content": prompt}], model, image)
            if not isinstance(result, dict):
                raise RunnerError("OCR result must be a JSON object")
            result["image"] = image.name
            result.setdefault("ocr_metadata", {})["genai_model"] = model
            result["ocr_metadata"]["method"] = "workflow_runner.ocr"
            _atomic_json(metadata / f"{image.stem}.json", result)
            written.append(image.name)
        except RunnerError as error:
            failures.append({"file": image.name, "error": str(error)})
    return {
        "operation": "ocr",
        "model": model,
        "processed": len(written),
        "skipped": len(imported) - len(pending),
        "failed": failures,
        "files_written": written,
    }


def _run_reinterpret(project: Path, model: str) -> dict[str, Any]:
    written = []
    failures = []
    for path in _metadata_files(project):
        try:
            current = _read_json(path)
            transcript = current.get("full_transcript", "")
            if not transcript:
                raise RunnerError("full_transcript is empty")
            prompt = f"{_common_rules()}\nReturn the complete metadata object, preserving image and full_transcript. Update only structured interpretation fields.\n{_schema_prompt()}\nExisting metadata:\n{json.dumps(current, ensure_ascii=False)}\nGlossary:\n{_glossary(project)}"
            result = _request_json([{"role": "user", "content": prompt}], model)
            if not isinstance(result, dict) or result.get("image") not in {None, current.get("image"), path.stem + ".jpg"}:
                raise RunnerError("reinterpretation returned an invalid image identity")
            result["image"] = current.get("image", result.get("image", path.stem + ".jpg"))
            result["full_transcript"] = transcript
            result.setdefault("ocr_metadata", {})["genai_model"] = model
            result["ocr_metadata"]["method"] = "workflow_runner.reinterpret"
            _atomic_json(path, result)
            written.append(path.name)
        except RunnerError as error:
            failures.append({"file": path.name, "error": str(error)})
    return {"operation": "reinterpret", "model": model, "processed": len(written), "failed": failures, "files_written": written}


def _run_map(project: Path, model: str) -> dict[str, Any]:
    metadata = [_read_json(path) for path in _metadata_files(project)]
    existing_path = project / "docs_logical_map.json"
    existing = _read_json(existing_path) if existing_path.exists() else {"schema_version": "2.0", "logical_documents": []}
    prompt = f"""{_common_rules()}
Return only a JSON object with schema_version and logical_documents.
Each logical document must have id, title, type, and images. Use only image names present in the metadata.
Preserve stable existing ids where possible. Do not modify metadata files.
Existing map:
{json.dumps(existing, ensure_ascii=False)}
Metadata transcripts and extracted fields:
{json.dumps(metadata, ensure_ascii=False)}
Glossary:
{_glossary(project)}"""
    result = _request_json([{"role": "user", "content": prompt}], model)
    if not isinstance(result, dict) or not isinstance(result.get("logical_documents"), list):
        raise RunnerError("map result must contain a logical_documents array")
    available = {item.get("image") for item in metadata}
    seen = set()
    for document in result["logical_documents"]:
        if not isinstance(document, dict) or not document.get("id") or not document.get("images"):
            raise RunnerError("map contains a document without id or images")
        for image in document["images"]:
            if image not in available:
                raise RunnerError(f"map references unknown image: {image}")
            if image in seen:
                raise RunnerError(f"image appears in more than one logical document: {image}")
            seen.add(image)
    result["schema_version"] = "2.0"
    _atomic_json(existing_path, result)
    return {"operation": "map", "model": model, "documents": len(result["logical_documents"]), "images_mapped": len(seen), "files_written": [existing_path.name]}


def main() -> int:
    if len(sys.argv) not in (3, 4):
        print("Usage: runner.py <ocr|reinterpret|map> <project_path> [model]", file=sys.stderr)
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
                summary = _run_ocr(project, model)
            elif operation == "reinterpret":
                summary = _run_reinterpret(project, model)
            else:
                summary = _run_map(project, model)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1 if summary.get("failed") else 0
    except RunnerError as error:
        print(json.dumps({"ok": False, "operation": operation, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    except Exception as error:
        print(json.dumps({"ok": False, "operation": operation, "error": f"unexpected runner error: {error}"}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
