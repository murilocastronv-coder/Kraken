FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.local/bin:/root/.cargo/bin:/usr/local/bin:${PATH}"
RUN curl --proto '=https' --tlsv1.2 -LsSf https://github.com/krakenfx/kraken-cli/releases/latest/download/kraken-cli-installer.sh | sh && kraken --version
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
ENV PORT=10000 PYTHONUNBUFFERED=1 PAPER_ONLY=true
CMD ["python", "app.py"]
