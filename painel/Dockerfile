FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Compiladores para pandas/numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Dependências Python
COPY painel/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Código do painel
COPY painel/app /app/app
COPY painel/gerar_hash.py /app/gerar_hash.py

# Script de extração (vive neste mesmo repositório)
COPY gera_csv.py /app/scripts/gera_csv.py

# Diretório de saída dos CSVs (volume)
RUN mkdir -p /data
ENV DATA_DIR=/data \
    SCRIPT_PATH=/app/scripts/gera_csv.py

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
