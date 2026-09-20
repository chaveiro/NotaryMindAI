# Workflow Runner

The workflow runner is the single provider-aware layer. It delegates actual model calls to `litellm` and does not rewrite model names or maintain a custom alias table.

## Contract

The runner is invoked as a small CLI worker:

```bash
python3 workflow_runner/runner.py ocr projects/demo_project
```

The runner accepts the operation and project directory, and optionally a model string. Model selection precedence is:

1. `NOTARYMIND_<OPERATION>_MODEL`
2. `NOTARYMIND_GENAI_MODEL`
3. the optional CLI model argument
4. the built-in default `claude-opus-4.8`

The model string is passed through as-is. There is no custom alias normalization layer.

## Current behavior

- `normalize_model_name()` returns the exact model string after trimming whitespace
- provider selection is still based on `GENAI_PROVIDER` and the model prefix when needed
- the worker owns provider-specific handling, including Copilot device-login prompts
- the API server remains generic and just streams worker output back to the browser

## Provider Setup

### GitHub Copilot

GitHub Copilot is handled via LiteLLM's own device login flow. Do not treat it as a standard `OPENAI_API_KEY` provider.

```bash
export GENAI_PROVIDER=copilot
export GITHUB_COPILOT_API_BASE="https://api.githubcopilot.com"
export NOTARYMIND_OCR_MODEL="github-copilot/claude-opus-4.8"
python3 workflow_runner/runner.py ocr projects/demo_project
```

If LiteLLM asks for a GitHub device code, the runner surfaces the exact device login text and the user completes authentication in the browser.

### OpenAI

```bash
export GENAI_PROVIDER=openai
export OPENAI_API_KEY="your-openai-key"
export OPENAI_API_BASE="https://api.openai.com/v1"
export NOTARYMIND_OCR_MODEL="gpt-4.1"
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
export NOTARYMIND_OCR_MODEL="gpt-4.1"
python3 workflow_runner/runner.py ocr projects/demo_project
```

### Vertex AI

```bash
export GENAI_PROVIDER=vertex_ai
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
export VERTEXAI_PROJECT="your-gcp-project"
export VERTEXAI_LOCATION="us-central1"
export NOTARYMIND_OCR_MODEL="gemini-2.0-flash"
python3 workflow_runner/runner.py ocr projects/demo_project
```

### Bedrock

```bash
export GENAI_PROVIDER=bedrock
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-east-1"
export NOTARYMIND_OCR_MODEL="anthropic.claude-3-5-sonnet-20241022-v2:0"
python3 workflow_runner/runner.py ocr projects/demo_project
```

### Ollama

```bash
export GENAI_PROVIDER=ollama
export OLLAMA_API_BASE="http://localhost:11434"
export NOTARYMIND_OCR_MODEL="llama3.1:8b"
python3 workflow_runner/runner.py ocr projects/demo_project
```

### LM Studio

```bash
export GENAI_PROVIDER=lmstudio
export OPENAI_API_KEY="lm-studio"
export OPENAI_API_BASE="http://localhost:1234/v1"
python3 workflow_runner/runner.py ocr projects/demo_project local-model
```

## Notes

- `litellm` is the only supported client layer
- the runner intentionally avoids custom model alias rewriting
- the server is generic and streams worker logs/results to the UI via SSE
- Copilot authentication is LiteLLM-managed, not a custom local token check
