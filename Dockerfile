# ./Dockerfile

FROM python:3.12-slim

# [CHANGED] '=' 양옆 공백 제거
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tini && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN python -m pip install --upgrade pip \
 && python -m pip install -e .[fastapi,reports]

COPY docker/entrypoint.sh /app/docker/entrypoint.sh
RUN chmod +x /app/docker/entrypoint.sh

ENTRYPOINT ["/usr/bin/tini","-g","--","/app/docker/entrypoint.sh"]