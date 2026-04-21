import json
import logging
import traceback
from datetime import datetime
from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import PlainTextResponse
from config import get_settings
from models import ReceivedMessageRecord, MessageType
from services.bigquery_service import get_bigquery_service

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.get("")
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
) -> PlainTextResponse:
    """Verifica el webhook con el token de WhatsApp."""
    settings = get_settings()
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return PlainTextResponse(content=hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("")
async def receive_webhook(request: Request) -> dict:
    """Recibe y procesa los mensajes entrantes del webhook de WhatsApp.

    IMPORTANTE: Siempre devuelve 200 OK a Meta. Si se responde con cualquier
    codigo que no sea 2xx, Meta reintentara el webhook repetidamente durante
    horas, lo que causaria registros duplicados en BigQuery.
    Los errores internos se registran pero no se propagan a Meta.
    """
    payload = await request.json()
    raw_payload = json.dumps(payload)
    
    # Log del payload recibido para depuración
    logger.info(f"Webhook recibido: {raw_payload}")

    try:
        entry = payload.get("entry", [])
        if not entry:
            logger.warning("Payload del webhook sin campo 'entry'")
            return {"status": "ok"}

        changes = entry[0].get("changes", [])
        if not changes:
            logger.warning("Entry del webhook sin campo 'changes'")
            return {"status": "ok"}

        value = changes[0].get("value", {})

        if "statuses" in value:
            statuses = value.get("statuses", [])
            bigquery_service = get_bigquery_service()
            for status_obj in statuses:
                msg_id = status_obj.get("id")
                msg_status = status_obj.get("status")
                if msg_id and msg_status:
                    error_details = None
                    if msg_status == "failed" and "errors" in status_obj:
                        error_details = json.dumps(status_obj.get("errors"))
                    
                    try:
                        bigquery_service.update_message_status(msg_id, msg_status, error_details)
                    except Exception as e:
                        logger.error(f"Error actualizando status desde webhook para {msg_id}: {e}")
                        
            if "messages" not in value:
                logger.info("Notificacion de estado (status) procesada")
                return {"status": "ok"}

        messages = value.get("messages", [])
        if not messages:
            logger.info("El webhook no contiene mensajes (probablemente es una notificacion de otro tipo)")
            return {"status": "ok"}

        bigquery_service = get_bigquery_service()

        for message in messages:
            record = _parse_message(message, raw_payload)
            if record:
                bigquery_service.insert_received_message(record)

    except Exception as e:
        # No re-lanzar el error: Meta retentaria el webhook si no recibe 200
        logger.error(f"Error procesando webhook: {str(e)}")
        logger.error(traceback.format_exc())
        pass

    return {"status": "ok"}


def _parse_message(message: dict, raw_payload: str) -> ReceivedMessageRecord | None:
    """Parsea un mensaje del webhook y lo convierte en un registro."""
    message_id = message.get("id")
    from_number = message.get("from")
    timestamp_str = message.get("timestamp")
    message_type = message.get("type", "text")

    if not all([message_id, from_number, timestamp_str]):
        logger.warning(f"Mensaje omitido por falta de datos requeridos: id={message_id}, from={from_number}, timestamp={timestamp_str}")
        return None

    timestamp = datetime.fromtimestamp(int(timestamp_str))
    content = _extract_message_content(message, message_type)

    media_id = None
    if message_type in ["image", "audio", "video", "document", "sticker"]:
        media_data = message.get(message_type, {})
        media_id = media_data.get("id")

    try:
        msg_type = MessageType(message_type)
    except ValueError:
        msg_type = MessageType.TEXT

    return ReceivedMessageRecord(
        message_id=message_id,
        from_number=from_number,
        message_type=msg_type.value,
        content=content,
        media_id=media_id,
        received_at=timestamp,
        raw_payload=raw_payload,
    )


def _extract_message_content(message: dict, message_type: str) -> str:
    """Extrae el contenido del mensaje segun su tipo."""
    if message_type == "text":
        return message.get("text", {}).get("body", "")
    elif message_type == "image":
        return message.get("image", {}).get("caption", "[image]")
    elif message_type == "video":
        return message.get("video", {}).get("caption", "[video]")
    elif message_type == "audio":
        return "[audio]"
    elif message_type == "document":
        return message.get("document", {}).get("filename", "[document]")
    elif message_type == "sticker":
        return "[sticker]"
    elif message_type == "location":
        loc = message.get("location", {})
        return f"lat:{loc.get('latitude')},lon:{loc.get('longitude')}"
    elif message_type == "contacts":
        return "[contacts]"
    elif message_type == "interactive":
        interactive = message.get("interactive", {})
        interactive_type = interactive.get("type", "")
        if interactive_type == "button_reply":
            return interactive.get("button_reply", {}).get("title", "")
        elif interactive_type == "list_reply":
            return interactive.get("list_reply", {}).get("title", "")
    return ""



