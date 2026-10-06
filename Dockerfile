FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.lock.txt ./
RUN pip install --require-hashes --no-cache-dir -r requirements.lock.txt
COPY pyproject.toml README.md LICENSE NOTICE THIRD_PARTY_NOTICES.md ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps . && \
    useradd --create-home --uid 10001 app && \
    mkdir -p /home/app/.local/share/telegram-readonly-mcp && \
    chown -R app:app /home/app/.local && \
    chmod 700 /home/app/.local/share/telegram-readonly-mcp
USER app
ENV TELEGRAM_SESSION_DIR=/home/app/.local/share/telegram-readonly-mcp
EXPOSE 8765
ENTRYPOINT ["telegram-mcp"]
CMD ["serve", "--transport", "http", "--host", "0.0.0.0"]
