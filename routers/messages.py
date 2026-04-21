from fastapi import APIRouter, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models import (
    SendMessageRequest,
    SendMessageResponse,
    TextContent,
    MessageType,
    MediaContent,
    InteractiveContent,
)
from services.whatsapp_service import get_whatsapp_service
from config import get_settings
from pydantic import BaseModel
from typing import Optional


class TemplateCreate(BaseModel):
    name: str
    text: str
    category: str = "MARKETING"
    language: str = "es"
    header_type: Optional[str] = None
    header_text: Optional[str] = None
    header_handle: Optional[str] = None
    footer_text: Optional[str] = None
    waba_id: Optional[str] = None


security = HTTPBearer()


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Verifica el token de autenticacion JWT."""
    token = credentials.credentials
    settings = get_settings()
    
    import jwt
    try:
        # Usamos el token original estático como clave secreta para firmar/validar
        payload = jwt.decode(token, settings.api_auth_token, algorithms=["HS256"])
        return payload
    except jwt.PyJWTError:
        # Fallback de compatibilidad por si se sigue usando el token duro (ej. dev local)
        if token != settings.api_auth_token:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return {"sub": "system"}


router = APIRouter(
    prefix="/messages", tags=["messages"], dependencies=[Depends(verify_token)]
)


@router.post("/templates")
async def create_template(request: TemplateCreate):
    """Crea una nueva plantilla en Meta API."""
    try:
        whatsapp_service = get_whatsapp_service()
        result = await whatsapp_service.create_template(
            name=request.name,
            text=request.text,
            category=request.category,
            language=request.language,
            header_type=request.header_type,
            header_text=request.header_text,
            header_handle=request.header_handle,
            footer_text=request.footer_text,
            waba_id=request.waba_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class BulkMessageRequest(BaseModel):
    """Solicitud para enviar mensajes masivos."""

    recipients: list[str]
    message_type: MessageType = MessageType.TEXT
    text: Optional[TextContent] = None
    image: Optional[MediaContent] = None
    video: Optional[MediaContent] = None
    audio: Optional[MediaContent] = None
    document: Optional[MediaContent] = None
    sticker: Optional[MediaContent] = None
    interactive: Optional[InteractiveContent] = None
    template_name: Optional[str] = None
    template_language: Optional[str] = "es"
    template_components: Optional[list] = None


class BulkMessageResponse(BaseModel):
    """Respuesta del envio masivo de mensajes."""

    total: int
    successful: int
    failed: int
    results: list[SendMessageResponse]


@router.post("/send", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest) -> SendMessageResponse:
    """Envia un mensaje individual a un destinatario."""
    try:
        whatsapp_service = get_whatsapp_service()
        response = await whatsapp_service.send_message(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send-bulk", response_model=BulkMessageResponse)
async def send_bulk_messages(request: BulkMessageRequest) -> BulkMessageResponse:
    """Envia mensajes a multiples destinatarios."""
    whatsapp_service = get_whatsapp_service()
    results = []
    successful = 0
    failed = 0

    for recipient in request.recipients:
        try:
            send_request = SendMessageRequest(
                to=recipient,
                message_type=request.message_type,
                text=request.text,
                image=request.image,
                video=request.video,
                audio=request.audio,
                document=request.document,
                sticker=request.sticker,
                interactive=request.interactive,
                template_name=request.template_name,
                template_language=request.template_language,
                template_components=request.template_components,
            )
            response = await whatsapp_service.send_message(send_request)
            results.append(response)
            successful += 1
        except Exception:
            failed += 1

    return BulkMessageResponse(
        total=len(request.recipients),
        successful=successful,
        failed=failed,
        results=results,
    )


@router.get("/templates/{name}/status")
async def get_template_status(name: str, waba_id: Optional[str] = None):
    """Obtiene el estado de una plantilla desde Meta API."""
    try:
        whatsapp_service = get_whatsapp_service()
        status_info = await whatsapp_service.get_template_status(name, waba_id)
        return status_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
