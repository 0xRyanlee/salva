FROM python:3.12-slim

WORKDIR /app

# Install Obscura headless browser (Apache 2.0)
# obscura-worker must stay alongside obscura for parallel scrape to work.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fL \
       "https://github.com/h4ckf0r0day/obscura/releases/latest/download/obscura-x86_64-linux.tar.gz" \
       | tar xz -C /usr/local/bin \
    && chmod +x /usr/local/bin/obscura /usr/local/bin/obscura-worker \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/*

COPY . .
RUN pip install --no-cache-dir -e ".[dev]"

EXPOSE 8765

ENV PYTHONUNBUFFERED=1
ENV OBSCURA_BIN=obscura

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8765"]
