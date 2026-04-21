from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from services.bigquery_service import get_bigquery_service
from services.whatsapp_service import get_whatsapp_service
from routers.messages import verify_token
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/settings", tags=["settings"], dependencies=[Depends(verify_token)])

class PhoneNumber(BaseModel):
    alias: str
    phone_number_id: str
    display_phone_number: Optional[str] = None
    waba_id: Optional[str] = None

@router.get("/phone-numbers")
async def get_phone_numbers():
    """Obtiene la lista de numeros de telefono configurados."""
    try:
        bq_service = get_bigquery_service()
        return bq_service.get_phone_numbers()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/phone-numbers")
async def add_phone_number(phone: PhoneNumber):
    """Agrega un nuevo numero de telefono."""
    try:
        bq_service = get_bigquery_service()
        bq_service.add_phone_number(
            phone.alias, 
            phone.phone_number_id, 
            phone.display_phone_number,
            phone.waba_id
        )
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/media/upload")
async def upload_media(
    file: UploadFile = File(...),
    phone_number_id: Optional[str] = Form(None)
):
    """Sube un archivo multimedia a Meta y devuelve el ID."""
    try:
        content = await file.read()
        whatsapp_service = get_whatsapp_service()
        media_id = await whatsapp_service.upload_media(
            content, 
            file.content_type, 
            phone_number_id
        )
        return {"id": media_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/media/upload-resumable")
async def upload_resumable_media_endpoint(
    file: UploadFile = File(...)
):
    """Sube un archivo multimedia a Meta vía Resumable Upload API para obtener un 'handle' exigido en la creación de templates."""
    try:
        content = await file.read()
        file_size = len(content)
        whatsapp_service = get_whatsapp_service()
        handle = await whatsapp_service.upload_resumable_media(
            content,
            file.content_type,
            file_size,
            file.filename
        )
        return {"handle": handle}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
