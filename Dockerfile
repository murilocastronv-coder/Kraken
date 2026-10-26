FROM rust:1.86-bookworm AS build
RUN apt-get update && apt-get install -y --no-install-recommends pkg-config libssl-dev build-essential ca-certificates && rm -rf /var/lib/apt/lists/*
RUN cargo install --git https://github.com/krakenfx/kraken-cli
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates libssl3 python3 python3-pip && rm -rf /var/lib/apt/lists/*
COPY --from=build /usr/local/cargo/bin/kraken /usr/local/bin/kraken
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --break-system-packages -r requirements.txt
COPY app.py .
ENV PORT=10000 PYTHONUNBUFFERED=1 PAPER_ONLY=true
CMD ["python3", "app.py"]
