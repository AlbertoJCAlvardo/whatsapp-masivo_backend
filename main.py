from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from routers import webhook, messages, history, chat, settings, auth
from services.bigquery_service import get_bigquery_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa los servicios al arrancar la aplicacion."""
    # get_bigquery_service() inicializaria BigQuery sincrónicamente, bloqueando el inicio.
    # Ahora se inicializará perezosamente en la primera solicitud.
    yield


app = FastAPI(
    title="WhatsApp Business API",
    description="API para enviar y recibir mensajes de WhatsApp Business con almacenamiento en BigQuery",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook.router)
app.include_router(messages.router)
app.include_router(history.router)
app.include_router(chat.router)
app.include_router(settings.router)
app.include_router(auth.router)


@app.get("/")
async def root() -> dict:
    """Endpoint raiz para verificar el estado de la API."""
    return {"status": "ok", "service": "whatsapp-business-api"}


@app.get("/health")
async def health_check() -> dict:
    """Endpoint de health check para Cloud Run."""
    return {"status": "healthy"}



