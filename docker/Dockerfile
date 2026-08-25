FROM python:3.12-slim

WORKDIR /app

# Non-root user
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin pika

COPY pyproject.toml README.md ./
COPY pika ./pika
COPY config ./config
COPY agents ./agents
COPY tools ./tools
COPY teams ./teams
COPY skills ./skills
COPY workflows ./workflows
COPY registry.yaml ./
COPY pika.yaml ./

RUN pip install --no-cache-dir -e . \
    && chown -R pika:pika /app

USER pika

EXPOSE 8080

CMD ["pika", "serve", "--host", "0.0.0.0", "--port", "8080"]
