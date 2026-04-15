# WhatsApp Masivo — Backend

API REST construida con **FastAPI** para enviar y recibir mensajes de WhatsApp Business, con almacenamiento en BigQuery.

## Stack

- Python 3.11 + FastAPI + Uvicorn
- Google Cloud BigQuery
- WhatsApp Business Cloud API
- Docker / Cloud Run

## Estructura

```
.
├── main.py            # Entry point FastAPI
├── config.py          # Configuración (pydantic-settings)
├── models.py          # Modelos Pydantic
├── routers/           # Endpoints (webhook, messages, history, chat, settings)
├── services/          # Servicios (BigQuery, WhatsApp)
├── Dockerfile
├── cloudbuild.yaml    # CI/CD en Google Cloud Build
├── deploy.sh          # Script de despliegue manual
└── .env.example       # Variables de entorno requeridas
```

## Variables de entorno

Copia `.env.example` a `.env` y rellena los valores:

```env
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_ACCESS_TOKEN=your_access_token
WHATSAPP_VERIFY_TOKEN=your_verify_token
GCP_PROJECT_ID=your_gcp_project_id
BIGQUERY_DATASET=whatsapp_messages
BIGQUERY_TABLE_SENT=sent_messages
BIGQUERY_TABLE_RECEIVED=received_messages
API_AUTH_TOKEN=your_secure_api_token
```

## Desarrollo local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # y rellena los valores
uvicorn main:app --reload --port 8000
```

La API queda disponible en http://localhost:8000  
Documentación interactiva: http://localhost:8000/docs

## Despliegue en Cloud Run

```bash
# Usando el script
export GCP_PROJECT_ID=tu-proyecto
bash deploy.sh

# O con Cloud Build
gcloud builds submit
```
