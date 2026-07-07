FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VERT_TIGE_HOST=0.0.0.0 \
    VERT_TIGE_PORT=8000

WORKDIR /app

COPY app.py ./
COPY static ./static
COPY tools ./tools

RUN mkdir -p /app/data /app/static/uploads

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=3).read(1)"

CMD ["python", "app.py"]
