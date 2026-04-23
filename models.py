from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class MessageType(str, Enum):
    """Tipos de mensaje soportados por WhatsApp."""

    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"
    STICKER = "sticker"
    LOCATION = "location"
    CONTACTS = "contacts"
    INTERACTIVE = "interactive"
    TEMPLATE = "template"


class MessageStatus(str, Enum):
    """Estados posibles de un mensaje."""

    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class TextContent(BaseModel):
    """Contenido de un mensaje de texto."""

    body: str


class MediaContent(BaseModel):
    """Contenido para mensajes multimedia (imagen, video, documento, audio, sticker)."""

    id: Optional[str] = None
    link: Optional[str] = None
    caption: Optional[str] = None
    filename: Optional[str] = None


class InteractiveReplyButton(BaseModel):
    """Boton de respuesta rapida."""
    id: str
    title: str


class InteractiveSectionRow(BaseModel):
    """Fila de una seccion en lista."""
    id: str
    title: str
    description: Optional[str] = None


class InteractiveSection(BaseModel):
    """Seccion de una lista."""
    title: str
    rows: list[InteractiveSectionRow]


class InteractiveAction(BaseModel):
    """Accion para mensajes interactivos."""
    buttons: Optional[list[dict]] = None
    button: Optional[str] = None
    sections: Optional[list[InteractiveSection]] = None


class InteractiveBody(BaseModel):
    """Cuerpo de mensaje interactivo."""
    text: str


class InteractiveHeader(BaseModel):
    """Encabezado de mensaje interactivo."""
    type: str = "text"
    text: Optional[str] = None
    image: Optional[MediaContent] = None
    video: Optional[MediaContent] = None
    document: Optional[MediaContent] = None


class InteractiveFooter(BaseModel):
    """Pie de mensaje interactivo."""
    text: str


class InteractiveContent(BaseModel):
    """Contenido para mensajes interactivos (botones, listas)."""
    type: str
    header: Optional[InteractiveHeader] = None
    body: InteractiveBody
    footer: Optional[InteractiveFooter] = None
    action: InteractiveAction


class SendMessageRequest(BaseModel):
    """Solicitud para enviar un mensaje."""

    to: str = Field(..., description="Numero de telefono del destinatario")
    from_phone_number_id: Optional[str] = Field(None, description="ID del numero de telefono desde el cual enviar")
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
    full_text: Optional[str] = None


class SendMessageResponse(BaseModel):
    """Respuesta al enviar un mensaje."""

    message_id: str
    status: str
    timestamp: datetime


class WebhookVerification(BaseModel):
    """Parametros de verificacion del webhook."""

    hub_mode: str = Field(..., alias="hub.mode")
    hub_challenge: str = Field(..., alias="hub.challenge")
    hub_verify_token: str = Field(..., alias="hub.verify_token")


class WebhookMessage(BaseModel):
    """Mensaje recibido en el webhook."""

    message_id: str
    from_number: str
    timestamp: datetime
    message_type: MessageType
    content: str
    media_id: Optional[str] = None


class SentMessageRecord(BaseModel):
    """Registro de mensaje enviado para BigQuery."""

    message_id: str
    from_number: str
    to_number: str
    message_type: str
    content: str
    status: str
    sent_at: datetime
    media_id: Optional[str] = None
    whatsapp_response: Optional[str] = None


class ReceivedMessageRecord(BaseModel):
    """Registro de mensaje recibido para BigQuery."""

    message_id: str
    from_number: str
    to_number: str
    message_type: str
    content: str
    media_id: Optional[str] = None
    received_at: datetime
    raw_payload: str



