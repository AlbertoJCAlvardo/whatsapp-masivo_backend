from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
import io
from services.bigquery_service import get_bigquery_service
from services.whatsapp_service import get_whatsapp_service
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

@router.post("/read/{phone_number}")
async def mark_chat_read(phone_number: str):
    try:
        bq_service = get_bigquery_service()
        bq_service.mark_chat_read(phone_number)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/media/{media_id}")
async def get_chat_media(media_id: str):
    try:
        wa_service = get_whatsapp_service()
        content, mime_type = await wa_service.download_media(media_id)
        return StreamingResponse(io.BytesIO(content), media_type=mime_type or "application/octet-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
