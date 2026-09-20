# Workflow Runner

The runner is intentionally small and easy to maintain. It keeps the project contract stable while abstracting the model/provider layer behind a single `LiteLLM`-style adapter.

## Why this is simpler

- one normalized model name layer
- one runtime config builder
- one request function for all model backends
- no duplicated provider logic for every operation

## Supported model patterns

Examples that are accepted by the runner:

- `claude-opus-4.8`
- `haiku-4.5`
- `copilot-gpt-4.1`
- `gpt-4.1`
- `local-model`

The runner normalizes them internally for the provider runtime.

The API invokes the runner without a model argument:

```bash
python3 -m workflow_runner ocr projects/demo_project
```

Model selection is internal. The precedence is `NOTARYMIND_<OPERATION>_MODEL`,
then `NOTARYMIND_GENAI_MODEL`, then the built-in default `claude-opus-4.8`.
The optional CLI model argument remains available for direct/manual runs.

## Provider examples

### Copilot

```bash
export GENAI_PROVIDER=copilot
export OPENAI_API_KEY="your-copilot-token"
export OPENAI_API_BASE="https://api.githubcopilot.com"
export NOTARYMIND_OCR_MODEL="github-copilot/claude-opus-4.8"
python3 -m workflow_runner ocr projects/demo_project
```

### LM Studio

```bash
export GENAI_PROVIDER=lmstudio
export OPENAI_API_KEY="lm-studio"
export OPENAI_API_BASE="http://localhost:1234/v1"
python3 -m workflow_runner ocr projects/demo_project local-model
```

### Anthropic Claude

```bash
export GENAI_PROVIDER=anthropic
export ANTHROPIC_API_KEY="your-key"
export ANTHROPIC_API_BASE="https://api.anthropic.com"
python3 -m workflow_runner ocr projects/demo_project claude-opus-4.8
```

## Model aliases

These aliases are mapped automatically:

- `github-copilot/claude-opus-4.8` -> Copilot Claude Opus 4.8
- `claude-opus-4.8` -> `anthropic/claude-opus-4-1-20250805`
- `haiku-4.5` -> `anthropic/claude-3-5-haiku-latest`
- `copilot-gpt-4.1` -> `openai/gpt-4.1`
- `local-model` -> `openai/local-model`

## Notes

- `litellm` is required and is the only supported client path.
- Install dependencies from `api/requirements.txt` before running the workflow runner.
- The runner no longer includes a direct HTTP fallback.
