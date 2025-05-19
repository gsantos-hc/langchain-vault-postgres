FROM python:3.13-slim

LABEL name="langchain-vault-demo" \
    version="0.1.0" \
    maintainer="Guilherme Santos (gsantos@hashicorp.com)"

ENV PIP_DEFAULT_TIMEOUT=100 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

COPY dist/*.whl /tmp/

RUN set -ex \
    && groupadd --system --gid 1000 demoapp \
    && useradd --system --uid 1000 --gid 1000 --create-home demoapp \
    && apt-get update \
    && apt-get upgrade -y \
    && pip install $(ls -1t /tmp/*.whl | head -1) -U \
    && rm -rf /tmp/*.whl \
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

COPY run.py /home/demoapp/

WORKDIR /home/demoapp/

ENV STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_LOGGER_LEVEL="info" \
    STREAMLIT_CLIENT_TOOLBAR_MODE="viewer" \
    STREAMLIT_CLIENT_SHOW_ERROR_DETAILS=false \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_THEME_BASE="light" \
    STREAMLIT_THEME_PRIMARY_COLOR="#3383f6"

CMD ["streamlit", "run", "run.py"]
USER demoapp
EXPOSE 8501
