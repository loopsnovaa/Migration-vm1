FROM docker.io/library/python:3.11-slim

WORKDIR /app

COPY counter.py /app/counter.py

CMD ["python", "-u", "/app/counter.py"]
