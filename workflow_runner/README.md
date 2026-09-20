# Workflow Runner

The runner is intentionally small and easy to maintain. It keeps the project contract stable while using `litellm` as a single provider adapter.

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
python3 workflow_runner/runner.py ocr projects/demo_project
```

Model selection is internal. The precedence is `NOTARYMIND_<OPERATION>_MODEL`,
then `NOTARYMIND_GENAI_MODEL`, then the built-in default `claude-opus-4.8`.
The optional CLI model argument remains available for direct/manual runs.

## Provider Setup

GitHub Copilot credentials only apply to the `copilot` provider. For OpenAI, Anthropic,
Vertex AI, Bedrock, Ollama, and Azure OpenAI you use that provider's own credentials or
local runtime setup.

### GitHub Copilot

GitHub Copilot does not give you an `OPENAI_API_KEY`. `litellm` handles Copilot through
its own authenticated GitHub Copilot flow. In practice, authenticate Copilot in your
editor or environment first, then run the workflow runner with the Copilot provider.

```bash
export GENAI_PROVIDER=copilot
export GITHUB_COPILOT_API_BASE="https://api.githubcopilot.com"
export NOTARYMIND_OCR_MODEL="github-copilot/claude-opus-4.8"
python3 workflow_runner/runner.py ocr projects/demo_project
```

If you are not already authenticated with GitHub Copilot, use one of the other providers
below instead. This runner does not mint a Copilot token for you.

### OpenAI

```bash
export GENAI_PROVIDER=openai
export OPENAI_API_KEY="your-openai-key"
export OPENAI_API_BASE="https://api.openai.com/v1"
export NOTARYMIND_OCR_MODEL="openai/gpt-4.1"
python3 workflow_runner/runner.py ocr projects/demo_project
```

### Anthropic

```bash
export GENAI_PROVIDER=anthropic
export ANTHROPIC_API_KEY="your-anthropic-key"
export ANTHROPIC_API_BASE="https://api.anthropic.com"
export NOTARYMIND_OCR_MODEL="claude-opus-4.8"
python3 workflow_runner/runner.py ocr projects/demo_project
```

### Azure OpenAI

```bash
export GENAI_PROVIDER=azure
export AZURE_API_KEY="your-azure-openai-key"
export AZURE_API_BASE="https://your-resource.openai.azure.com"
export AZURE_API_VERSION="2024-10-21"
export NOTARYMIND_OCR_MODEL="azure/gpt-4.1"
python3 workflow_runner/runner.py ocr projects/demo_project
```

### Vertex AI

```bash
export GENAI_PROVIDER=vertex_ai
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
export VERTEXAI_PROJECT="your-gcp-project"
export VERTEXAI_LOCATION="us-central1"
export NOTARYMIND_OCR_MODEL="vertex_ai/gemini-2.0-flash"
python3 workflow_runner/runner.py ocr projects/demo_project
```

### Bedrock

```bash
export GENAI_PROVIDER=bedrock
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-east-1"
export NOTARYMIND_OCR_MODEL="bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0"
python3 workflow_runner/runner.py ocr projects/demo_project
```

### Ollama

```bash
export GENAI_PROVIDER=ollama
export OLLAMA_API_BASE="http://localhost:11434"
export NOTARYMIND_OCR_MODEL="ollama_chat/llama3.1:8b"
python3 workflow_runner/runner.py ocr projects/demo_project
```

### LM Studio

```bash
export GENAI_PROVIDER=lmstudio
export OPENAI_API_KEY="lm-studio"
export OPENAI_API_BASE="http://localhost:1234/v1"
python3 workflow_runner/runner.py ocr projects/demo_project local-model
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
