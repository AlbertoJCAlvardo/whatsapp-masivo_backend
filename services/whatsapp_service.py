import json
import logging
from datetime import datetime
from typing import Any
import httpx
from models import SendMessageRequest, SendMessageResponse, SentMessageRecord
from config import get_settings
from services.bigquery_service import get_bigquery_service

logger = logging.getLogger(__name__)



class WhatsAppService:
    """Servicio para interactuar con la API de WhatsApp Business."""

    def __init__(self):
        """Inicializa el servicio con la configuracion necesaria."""
        self.settings = get_settings()
        self.default_phone_number_id = self.settings.whatsapp_phone_number_id
        self.base_url_template = f"{self.settings.whatsapp_api_url}/{{phone_number_id}}"
        self.headers = {
            "Authorization": f"Bearer {self.settings.whatsapp_access_token}",
            "Content-Type": "application/json",
        }

    def _get_base_url(self, phone_number_id: str = None) -> str:
        """Obtiene la URL base para el ID de telefono especificado o el predeterminado."""
        pid = phone_number_id if phone_number_id else self.default_phone_number_id
        return self.base_url_template.format(phone_number_id=pid)

    def _build_text_payload(self, request: SendMessageRequest) -> dict:
        """Construye el payload para un mensaje de texto."""
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": request.to,
            "type": "text",
            "text": {"body": request.text.body},
        }

    def _build_template_payload(self, request: SendMessageRequest) -> dict:
        """Construye el payload para un mensaje de plantilla."""
        payload = {
            "messaging_product": "whatsapp",
            "to": request.to,
            "type": "template",
            "template": {
                "name": request.template_name,
                "language": {"code": request.template_language},
            },
        }
        if request.template_components:
            payload["template"]["components"] = request.template_components
        return payload

    def _build_media_payload(self, request: SendMessageRequest, media_type: str) -> dict:
        """Construye el payload para mensajes multimedia."""
        media_content = getattr(request, media_type)
        if not media_content:
            raise ValueError(f"Content for {media_type} is missing")

        media_object = {}
        if media_content.id:
            media_object["id"] = media_content.id
        elif media_content.link:
            media_object["link"] = media_content.link

        if media_content.caption:
            media_object["caption"] = media_content.caption
        if media_content.filename and media_type == "document":
            media_object["filename"] = media_content.filename

        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": request.to,
            "type": media_type,
            media_type: media_object,
        }

    def _build_interactive_payload(self, request: SendMessageRequest) -> dict:
        """Construye el payload para mensajes interactivos."""
        if not request.interactive:
            raise ValueError("Interactive content is missing")

        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": request.to,
            "type": "interactive",
            "interactive": request.interactive.model_dump(exclude_none=True),
        }

    async def upload_media(self, file_content: bytes, mime_type: str, phone_number_id: str = None) -> str:
        """Sube un archivo multimedia a la API de WhatsApp y devuelve el ID."""
        url = f"{self._get_base_url(phone_number_id)}/media"
        
        files = {"file": ("file", file_content, mime_type)}
        data = {"messaging_product": "whatsapp"}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={"Authorization": self.headers["Authorization"]}, # No Content-Type for multipart
                files=files,
                data=data,
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json()["id"]

    async def upload_resumable_media(self, file_content: bytes, mime_type: str, file_size: int, filename: str) -> str:
        """Sube un archivo usando la Resumable Upload API para obtener un 'handle'."""
        if not self.settings.whatsapp_app_id:
            raise ValueError("WHATSAPP_APP_ID no está configurado en las variables de entorno.")

        # Paso 1: Crear sesión de carga
        session_url = f"https://graph.facebook.com/v19.0/{self.settings.whatsapp_app_id}/uploads"
        params = {
            "file_length": str(file_size),
            "file_type": mime_type,
            "access_token": self.settings.whatsapp_access_token
        }
        
        async with httpx.AsyncClient() as client:
            session_resp = await client.post(session_url, params=params, timeout=30.0)
            session_resp.raise_for_status()
            session_id = session_resp.json()["id"]

            # Paso 2: Subir data
            upload_url = f"https://graph.facebook.com/v19.0/{session_id}"
            headers = {
                "Authorization": f"OAuth {self.settings.whatsapp_access_token}",
                "file_offset": "0"
            }
            upload_resp = await client.post(
                upload_url,
                headers=headers,
                content=file_content,
                timeout=60.0
            )
            upload_resp.raise_for_status()
            return upload_resp.json()["h"]

    async def send_message(self, request: SendMessageRequest) -> SendMessageResponse:
        """Envia un mensaje a traves de la API de WhatsApp."""
        if request.message_type.value == "template":
            payload = self._build_template_payload(request)
        elif request.message_type.value == "text":
            payload = self._build_text_payload(request)
        elif request.message_type.value == "interactive":
            payload = self._build_interactive_payload(request)
        elif request.message_type.value in [
            "image",
            "video",
            "document",
            "audio",
            "sticker",
        ]:
            payload = self._build_media_payload(request, request.message_type.value)
        else:
            raise ValueError(f"Unsupported message type: {request.message_type.value}")

        url = f"{self._get_base_url(request.from_phone_number_id)}/messages"

        logger.info(f"Enviando mensaje a WhatsApp API: to={request.to}, type={request.message_type}")
        logger.debug(f"URL: {url}")
        logger.debug(f"Payload: {json.dumps(payload)}")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Error de HTTP al enviar mensaje: {e.response.status_code} - {e.response.text}")
                raise e
            except Exception as e:
                logger.error(f"Error inesperado al enviar mensaje: {str(e)}")
                raise e

        message_id = data["messages"][0]["id"]
        timestamp = datetime.utcnow()

        content = self._extract_content(request)
        record = SentMessageRecord(
            message_id=message_id,
            to_number=request.to,
            message_type=request.message_type.value,
            content=content,
            status="sent",
            sent_at=timestamp,
            whatsapp_response=json.dumps(data),
        )

        bigquery_service = get_bigquery_service()
        bigquery_service.insert_sent_message(record)

        return SendMessageResponse(
            message_id=message_id,
            status="sent",
            timestamp=timestamp,
        )

    async def get_template_status(self, template_name: str, waba_id: str = None) -> dict:
        """Consulta el estado de una plantilla en Meta."""
        target_waba = waba_id or self.settings.whatsapp_business_account_id
        if not target_waba:
            return {"status": "ERROR", "detail": "WABA ID no configurado"}

        url = f"{self.settings.whatsapp_api_url}/{target_waba}/message_templates"
        
        params = {"name": template_name}
        
        async with httpx.AsyncClient() as client:
            try:
                print(f"DEBUG: Consultando status de plantilla Meta...")
                print(f"DEBUG: URL: {url}")
                
                response = await client.get(
                    url,
                    headers=self.headers,
                    params=params,
                    timeout=10.0,
                )
                print(f"DEBUG: Meta Status Response: {response.text}")
                response.raise_for_status()
                data = response.json()
                
                # Meta devuelve una lista en 'data'
                templates = data.get("data", [])
                if not templates:
                    return {"status": "NOT_FOUND"}
                
                # Buscamos la que coincida exactamente por nombre
                target = next((t for t in templates if t.get("name") == template_name), None)
                if not target:
                    return {"status": "NOT_FOUND"}
                
                return {
                    "status": target.get("status"),
                    "name": target.get("name"),
                    "id": target.get("id"),
                    "category": target.get("category")
                }
            except Exception as e:
                logger.error(f"Error al consultar status de plantilla '{template_name}': {str(e)}")
                if hasattr(e, 'response') and e.response:
                    logger.error(f"Meta Error Response: {e.response.text}")
                return {"status": "ERROR", "detail": str(e)}

    async def create_template(self, name: str, text: str, category: str = "MARKETING", language: str = "es", header_type: str = None, header_text: str = None, header_handle: str = None, footer_text: str = None, waba_id: str = None) -> dict:
        """Registra una nueva plantilla en la cuenta de WhatsApp Business."""
        target_waba = waba_id or self.settings.whatsapp_business_account_id
        if not target_waba:
            raise Exception("WABA ID no configurado")
            
        url = f"{self.settings.whatsapp_api_url}/{target_waba}/message_templates"
        
        import re
        body_vars = re.findall(r'\{\{\d+\}\}', text)
        body_component = {
            "type": "BODY",
            "text": text
        }
        if body_vars:
            body_component["example"] = {
                "body_text": [["Variable"] * len(body_vars)]
            }
            
        components = [body_component]
        
        if header_type:
            if header_type.upper() == "TEXT" and header_text:
                components.insert(0, {
                    "type": "HEADER",
                    "format": "TEXT",
                    "text": header_text
                })
            elif header_type.upper() in ["IMAGE", "VIDEO", "DOCUMENT"]:
                header_comp = {
                    "type": "HEADER",
                    "format": header_type.upper()
                }
                if header_handle:
                    header_comp["example"] = {
                        "header_handle": [header_handle]
                    }
                components.insert(0, header_comp)
                
        if footer_text:
            components.append({
                "type": "FOOTER",
                "text": footer_text
            })
            
        payload = {
            "name": name,
            "category": category,
            "allow_category_change": True,
            "language": language,
            "components": components
        }
        
        async with httpx.AsyncClient() as client:
            try:
                # Depuracion profunda
                debug_payload = payload.copy()
                print(f"DEBUG: Intentando registrar plantilla Meta...")
                print(f"DEBUG: URL: {url}")
                print(f"DEBUG: Payload: {json.dumps(debug_payload)}")
                
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                # Log de respuesta para depuracion
                print(f"DEBUG: Meta Template Create Response: {response.text}")
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException:
                logger.error("Tiempo de espera agotado (Timeout) al conectar con Meta.")
                raise Exception("Meta: Tiempo de espera agotado. Reintenta en unos momentos.")
            except httpx.NetworkError as ne:
                logger.error(f"Error de red al conectar con Meta: {str(ne)}")
                raise Exception(f"Meta: Error de conexion de red: {str(ne)}")
            except Exception as e:
                logger.error(f"Error al crear plantilla Meta: {str(e)}")
                if hasattr(e, 'response') and e.response:
                    error_data = e.response.json()
                    logger.error(f"Meta API Error Detail: {error_data}")
                    meta_error = error_data.get('error', {})
                    msg = meta_error.get('error_user_msg') or meta_error.get('message') or str(e)
                    raise Exception(f"Meta: {msg}")
                raise e

    def _extract_content(self, request: SendMessageRequest) -> str:
        """Extrae el contenido del mensaje segun su tipo."""
        if request.message_type.value == "text" and request.text:
            return request.text.body
        elif request.message_type.value == "template":
            return request.full_text if request.full_text else f"template:{request.template_name}"
        elif request.message_type.value in [
            "image",
            "video",
            "document",
            "audio",
            "sticker",
        ]:
            media = getattr(request, request.message_type.value)
            return f"{request.message_type.value}:{media.link or media.id}"
        elif request.message_type.value == "interactive" and request.interactive:
            return f"interactive:{request.interactive.type}"
        return ""

    async def send_bulk_messages(
        self, requests: list[SendMessageRequest]
    ) -> list[SendMessageResponse]:
        """Envia multiples mensajes de forma concurrente."""
        responses = []
        for request in requests:
            response = await self.send_message(request)
            responses.append(response)
        return responses


_whatsapp_service: WhatsAppService | None = None


def get_whatsapp_service() -> WhatsAppService:
    """Obtiene la instancia singleton del servicio de WhatsApp."""
    global _whatsapp_service
    if _whatsapp_service is None:
        _whatsapp_service = WhatsAppService()
    return _whatsapp_service



