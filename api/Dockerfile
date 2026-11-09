# Imagen de la API de riesgo (contexto de build: raíz del proyecto)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 1) dependencias primero: esta capa se reutiliza mientras requirements.txt no cambie
COPY api/requirements.txt .
RUN pip install -r requirements.txt

# 2) código y modelo entrenado
COPY features.py features.py
COPY api/ api/
COPY models/ models/

# 3) no correr como root
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)" || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
