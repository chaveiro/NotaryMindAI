# Docker build and run

This directory contains the container image used by the NotaryMindAI API and the
supporting Docker documentation.

## Build the image

From the repository root:

```bash
./build_docker.sh
```

Or directly:

```bash
docker build -f docker/Dockerfile -t notarymindai:latest .
```

## Run the API in a container

```bash
docker run --rm \
  -p 8787:8787 \
  -v notarymindai-projects:/workspace/projects \
  --env PORT=8787 \
  --env GENAI_PROVIDER=copilot \
  --env GITHUB_COPILOT_API_BASE=https://api.githubcopilot.com \
  --env NOTARYMIND_OCR_MODEL=github_copilot/claude-opus-4.8 \
  --env NOTARYMIND_INTERPRET_MODEL=github_copilot/claude-opus-4.8 \
  --env NOTARYMIND_MAP_MODEL=github_copilot/claude-opus-4.8 \
  notarymindai:latest
```

The service starts the Flask API on port 8787.

The image includes the application code plus a bundled seed copy of `projects/demo`.
When you run the container with a Docker volume mounted to `/workspace/projects`,
the default startup command copies the seed `demo` project into that volume if it
is missing.

## Common environment variables

```bash
GENAI_PROVIDER=copilot
GITHUB_COPILOT_API_BASE=https://api.githubcopilot.com
OPENAI_API_BASE=https://api.openai.com
ANTHROPIC_API_BASE=https://api.anthropic.com

NOTARYMIND_OCR_MODEL=github_copilot/claude-opus-4.8
NOTARYMIND_INTERPRET_MODEL=github_copilot/haiku-4.5
NOTARYMIND_MAP_MODEL=github_copilot/haiku-4.5
```

You can also set:

```bash
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
```

> GitHub Copilot is handled through LiteLLM device-login flow; it is not a plain `OPENAI_API_KEY` flow.

## Notes

- The container runs from the repository root at `/workspace`.
- Application code is baked into the image.
- Runtime-created projects persist in whichever Docker volume you mount to `/workspace/projects`.
- The container startup command seeds `demo` into that volume automatically on first start.
- If you are debugging locally, use the same environment variables as the host process to ensure model selection matches the worker configuration.
