from __future__ import annotations

import base64
import json
import mimetypes
import os
import tempfile
from pathlib import Path
from typing import Any

import litellm  # type: ignore

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
COPILOT_API_BASE = "https://api.githubcopilot.com"
DEFAULT_OPENAI_BASE = "https://api.openai.com"
DEFAULT_ANTHROPIC_BASE = "https://api.anthropic.com"
DEFAULT_MODEL = "github_copilot/claude-opus-4.8"


class RunnerError(RuntimeError):
    """A user-actionable workflow failure."""


def env_name(operation: str) -> str:
    return os.environ.get(f"NOTARYMIND_{operation.upper()}_MODEL", "").strip()


def selected_model(operation: str, cli_model: str) -> str:
    return env_name(operation) or os.environ.get("NOTARYMIND_GENAI_MODEL", "").strip() or cli_model or DEFAULT_MODEL


def build_runtime_config(model: str) -> dict[str, Any]:
    normalized = (model or "").strip()
    provider_hint = os.environ.get("GENAI_PROVIDER", "openai").strip().lower()
    request_kwargs: dict[str, Any] = {}

    if provider_hint in {"anthropic", "claude"} or normalized.startswith("anthropic/"):
        provider = "anthropic"
        api_key_name = "ANTHROPIC_API_KEY"
        api_base = os.environ.get("ANTHROPIC_API_BASE", os.environ.get("ANTHROPIC_BASE_URL", DEFAULT_ANTHROPIC_BASE)).rstrip("/")
    elif provider_hint in {"azure", "azure_openai", "azure-openai"} or normalized.startswith("azure/"):
        provider = "azure"
        api_key_name = "AZURE_API_KEY"
        api_base = os.environ.get("AZURE_API_BASE", "").rstrip("/")
        api_version = os.environ.get("AZURE_API_VERSION", "").strip()
        if api_version:
            request_kwargs["api_version"] = api_version
    elif provider_hint in {"vertex", "vertex_ai", "vertexai"} or normalized.startswith("vertex_ai/"):
        provider = "vertex_ai"
        api_key_name = ""
        api_base = ""
        vertex_project = os.environ.get("VERTEXAI_PROJECT", os.environ.get("VERTEX_PROJECT", "")).strip()
        vertex_location = os.environ.get("VERTEXAI_LOCATION", os.environ.get("VERTEX_LOCATION", "")).strip()
        if vertex_project:
            request_kwargs["vertex_project"] = vertex_project
        if vertex_location:
            request_kwargs["vertex_location"] = vertex_location
    elif provider_hint in {"bedrock", "aws", "amazon-bedrock"} or normalized.startswith("bedrock/"):
        provider = "bedrock"
        api_key_name = ""
        api_base = ""
        aws_region = os.environ.get("AWS_REGION_NAME", os.environ.get("AWS_REGION", "")).strip()
        if aws_region:
            request_kwargs["aws_region_name"] = aws_region
        aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
        aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()
        aws_session_token = os.environ.get("AWS_SESSION_TOKEN", "").strip()
        if aws_access_key_id:
            request_kwargs["aws_access_key_id"] = aws_access_key_id
        if aws_secret_access_key:
            request_kwargs["aws_secret_access_key"] = aws_secret_access_key
        if aws_session_token:
            request_kwargs["aws_session_token"] = aws_session_token
    elif provider_hint in {"ollama"} or normalized.startswith(("ollama/", "ollama_chat/")):
        provider = "ollama"
        api_key_name = ""
        api_base = os.environ.get("OLLAMA_API_BASE", os.environ.get("OPENAI_API_BASE", "http://localhost:11434")).rstrip("/")
    elif provider_hint in {"copilot", "githubcopilot", "github_copilot"} or normalized.startswith(("copilot/", "github-copilot/", "github_copilot/")):
        provider = "github_copilot"
        api_key_name = ""
        api_base = os.environ.get("GITHUB_COPILOT_API_BASE", os.environ.get("OPENAI_API_BASE", os.environ.get("OPENAI_BASE_URL", "https://api.enterprise.githubcopilot.com"))).rstrip("/")
    elif provider_hint in {"lmstudio", "local"}:
        provider = "openai"
        api_key_name = "OPENAI_API_KEY"
        api_base = os.environ.get("OPENAI_API_BASE", os.environ.get("OPENAI_BASE_URL", "http://localhost:1234/v1")).rstrip("/")
    else:
        provider = "openai"
        api_key_name = "OPENAI_API_KEY"
        api_base = os.environ.get("OPENAI_API_BASE", os.environ.get("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE)).rstrip("/")

    return {
        "provider": provider,
        "model": normalized,
        "api_key_name": api_key_name,
        "api_key": os.environ.get(api_key_name, "").strip(),
        "api_base": api_base,
        "request_kwargs": request_kwargs,
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

    if config["api_key_name"] and not config["api_key"]:
        raise RunnerError(f"{config['api_key_name']} is not configured")

    try:
        completion_kwargs: dict[str, Any] = {
            "model": config["model"],
            "messages": _litellm_payload(messages, image, provider),
            "temperature": 0,
            "max_tokens": int(os.environ.get("GENAI_MAX_TOKENS", "12000")),
        }
        if config["api_key"]:
            completion_kwargs["api_key"] = config["api_key"]
        if config["api_base"]:
            completion_kwargs["api_base"] = config["api_base"]
        if provider != "anthropic":
            completion_kwargs["response_format"] = {"type": "json_object"}
        completion_kwargs.update(config.get("request_kwargs", {}))

        response = litellm.completion(**completion_kwargs)
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
