from fastapi import APIRouter, HTTPException, Depends
from services.bigquery_service import get_bigquery_service
from routers.messages import verify_token

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(verify_token)])

@router.get("/contacts")
async def get_contacts():
    """Obtiene la lista de contactos que han interactuado."""
    try:
        bq_service = get_bigquery_service()
        contacts = bq_service.get_contacts()
        return contacts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/messages/{phone_number}")
async def get_chat_history(phone_number: str):
    """Obtiene el historial de mensajes con un numero especifico."""
    try:
        bq_service = get_bigquery_service()
        history = bq_service.get_chat_history(phone_number)
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
