FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/jurisdata
COPY requirements.txt .
RUN pip install -r requirements.txt && useradd --system --uid 10001 --home /srv/jurisdata jurisdata
COPY app ./app

USER jurisdata
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/saude').status == 200 else 1)"

# --no-access-log: o log de acesso do servidor gravaria URLs; a trilha oficial é a auditoria do sistema.
# FORWARDED_ALLOW_IPS deve conter o IP do proxy reverso (TLS) para registrar o IP real do usuário.
CMD ["uvicorn", "app.main:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--proxy-headers"]
