# Docker build and run

This directory contains the container image used by the NotaryMindAI API and the local compose setup.

## Build the image

From the repository root:

```bash
./build_docker.sh
```

Or directly:

```bash
docker build -f docker-compose/Dockerfile -t notarymindai:latest .
```

## Run the API in a container

```bash
docker run --rm \
  -p 8787:8787 \
  --env PORT=8787 \
  --env GENAI_PROVIDER=copilot \
  --env GITHUB_COPILOT_API_BASE=https://api.githubcopilot.com \
  --env NOTARYMIND_OCR_MODEL=github-copilot/claude-opus-4.8 \
  --env NOTARYMIND_INTERPRET_MODEL=github-copilot/haiku-4.5 \
  --env NOTARYMIND_MAP_MODEL=github-copilot/haiku-4.5 \
  notarymindai:latest
```

The service starts the Flask API on port 8787.

## Compose

```bash
docker compose -f docker-compose/docker-compose.yml up --build
```

This uses the same Dockerfile and loads environment values from the shell or a `.env` file.

## Common environment variables

```bash
GENAI_PROVIDER=copilot
GITHUB_COPILOT_API_BASE=https://api.githubcopilot.com
OPENAI_API_BASE=https://api.openai.com
ANTHROPIC_API_BASE=https://api.anthropic.com

NOTARYMIND_OCR_MODEL=github-copilot/claude-opus-4.8
NOTARYMIND_INTERPRET_MODEL=github-copilot/haiku-4.5
NOTARYMIND_MAP_MODEL=github-copilot/haiku-4.5
```

You can also set:

```bash
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
```

> GitHub Copilot is handled through LiteLLM device-login flow; it is not a plain `OPENAI_API_KEY` flow.

## Notes

- The container runs from the repository root at `/workspace`.
- Project files live under the mounted repository tree.
- If you are debugging locally, use the same environment variables as the host process to ensure model selection matches the worker configuration.
