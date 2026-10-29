# Imagen común de los tres microservicios: se elige el servicio con --build-arg SERVICIO=<carpeta> y ENTRADA=<módulo:objeto>.
FROM python:3.13-slim

ARG SERVICIO
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY servicios/${SERVICIO}/ ./

RUN useradd --system --uid 10001 --no-create-home svc
USER svc

EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"
CMD ["sh", "-c", "exec uvicorn ${ENTRADA} --host 0.0.0.0 --port 8000"]
