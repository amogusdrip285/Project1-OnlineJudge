# PLACEHOLDER (Person A, Day 0) — Person B replaces this with the real judge image
# (g++, python3, sandboxing). It only exists so `docker compose up` works on Day 0.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY judge ./judge

RUN useradd --create-home --uid 10002 judge
USER judge

CMD ["python", "-m", "judge.main"]
