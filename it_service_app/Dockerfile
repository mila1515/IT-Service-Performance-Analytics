FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && useradd --create-home --uid 10001 analyst

# Code de l'application, son logo et sa configuration Streamlit (port 8510, thème, taille d'import).
COPY --chown=analyst:analyst app.py preparation.py indicateurs.py /app/
COPY --chown=analyst:analyst assets/ /app/assets/
COPY --chown=analyst:analyst .streamlit/ /app/.streamlit/
USER analyst

EXPOSE 8510
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8510/_stcore/health', timeout=2)"

CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8510", "--server.headless=true", "--server.fileWatcherType=none", "--browser.gatherUsageStats=false"]
