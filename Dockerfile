FROM python:3.11-slim

WORKDIR /app

# Instala dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el código del backend
COPY . .

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Cloud Run expone el puerto indicado en $PORT (por defecto 8080)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]

