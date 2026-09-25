FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY api /workspace/api
COPY ui /workspace/ui
COPY workflow_runner /workspace/workflow_runner
COPY skills/transcript /workspace/skills/transcript
COPY projects/demo /opt/notarymindai-seed/projects/demo

RUN mkdir -p /workspace/projects

EXPOSE 8787

CMD ["sh", "-lc", "mkdir -p /workspace/projects && if [ -d /opt/notarymindai-seed/projects/demo ] && [ ! -e /workspace/projects/demo ]; then cp -a /opt/notarymindai-seed/projects/demo /workspace/projects/demo; fi && exec python3 api/server.py"]
