# Imagen de la interfaz Streamlit (contexto de build: raíz del proyecto)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY ui/requirements.txt .
RUN pip install -r requirements.txt

COPY .streamlit/ .streamlit/
COPY ui/ ui/
COPY data/demo/ data/demo/
COPY reports/figures/ reports/figures/
COPY reports/comparacion_modelos.csv reports/

RUN useradd --create-home appuser
USER appuser

EXPOSE 8501
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=2)" || exit 1

CMD ["streamlit", "run", "ui/app.py", "--server.address=0.0.0.0", "--server.port=8501", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
