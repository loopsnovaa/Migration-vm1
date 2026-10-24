FROM ubuntu:22.04

RUN apt-get update && \
    apt-get install -y python3 dmtcp && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY counter.py /app/counter.py

CMD ["sleep", "infinity"]

