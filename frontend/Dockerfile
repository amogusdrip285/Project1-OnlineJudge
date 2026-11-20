# PLACEHOLDER (Person A, Day 0) — Person C replaces this with the Vite + React app.
# It only serves a static page on port 5173 so `docker compose up` works on Day 0.
FROM python:3.12-alpine

WORKDIR /site
COPY placeholder/ ./

RUN adduser -D -u 10003 web
USER web

EXPOSE 5173
CMD ["python", "-m", "http.server", "5173", "--bind", "0.0.0.0"]
