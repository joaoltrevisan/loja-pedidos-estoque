FROM python:3.12.15-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    RUFF_CACHE_DIR=/tmp/ruff

WORKDIR /app
# Imagem de desenvolvimento: inclui o Ruff para as verificacoes documentadas.
COPY requirements.lock /app/requirements.lock
RUN python -m pip install --no-cache-dir -r requirements.lock \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app
COPY . /app
USER app

EXPOSE 8000
ENTRYPOINT ["python", "manage.py"]
CMD ["runserver", "0.0.0.0:8000", "--noreload"]
