# WhatsApp Masivo - Backend

API REST construida con FastAPI (Python) que actua como intermediario entre el panel de administracion (frontend), la API oficial de WhatsApp Business Cloud de Meta, y Google BigQuery como base de datos de registros.

Este documento esta dirigido a cualquier persona del equipo que necesite entender como funciona el sistema, independientemente de si ha trabajado en el codigo anteriormente.

---

## Descripcion general del sistema

El backend cumple tres responsabilidades principales:

1. **Envio de mensajes**: Recibe instrucciones del frontend (ya sea para un mensaje individual o una campana masiva) y las ejecuta llamando a la API de WhatsApp de Meta.

2. **Recepcion de mensajes entrantes (Webhook)**: Cuando un usuario de WhatsApp responde al numero de la empresa, Meta notifica a esta API en tiempo real. El backend procesa ese mensaje y lo almacena en BigQuery.

3. **Almacenamiento y consulta de historial**: Todos los mensajes enviados y recibidos se guardan en Google BigQuery. Desde ahi se pueden consultar por numero de telefono, ver estadisticas de campanas, y obtener la lista de contactos que han interactuado.

---

## Tecnologias utilizadas

| Tecnologia | Version | Proposito |
|---|---|---|
| Python | 3.11 | Lenguaje base |
| FastAPI | >= 0.100 | Framework web y definicion de endpoints |
| Uvicorn | >= 0.23 | Servidor ASGI para ejecutar la aplicacion |
| Pydantic | v2 | Validacion y serializacion de datos |
| httpx | >= 0.24 | Cliente HTTP asincrono para llamar a la API de Meta |
| google-cloud-bigquery | >= 3.11 | Escritura y consulta del historial en BigQuery |
| Docker | - | Contenedorizacion para despliegue |

---

## Estructura del proyecto

```
whatsapp_masivo_backend/
|
|-- main.py                  # Punto de entrada de la aplicacion. Configura FastAPI, CORS y registra todos los routers.
|-- config.py                # Carga y valida las variables de entorno usando pydantic-settings.
|-- models.py                # Define todos los modelos de datos (mensajes, respuestas, registros de BigQuery).
|
|-- routers/                 # Contiene los endpoints agrupados por funcionalidad.
|   |-- messages.py          # Envio de mensajes individuales y masivos.
|   |-- webhook.py           # Recepcion y procesamiento de mensajes entrantes de WhatsApp.
|   |-- history.py           # Consulta de estadisticas de campanas pasadas.
|   |-- chat.py              # Consulta de contactos e historial de conversacion por numero.
|   |-- settings.py          # Gestion de numeros de telefono y subida de archivos multimedia.
|
|-- services/                # Logica de negocio y comunicacion con servicios externos.
|   |-- whatsapp_service.py  # Llama a la API de Meta para enviar mensajes y subir archivos.
|   |-- bigquery_service.py  # Interactua con BigQuery: crea tablas, inserta y consulta registros.
|
|-- Dockerfile               # Instrucciones para construir la imagen del contenedor.
|-- cloudbuild.yaml          # Configuracion de CI/CD para Google Cloud Build.
|-- deploy.sh                # Script alternativo de despliegue manual desde la terminal.
|-- requirements.txt         # Lista de dependencias de Python.
|-- .env.example             # Plantilla con las variables de entorno requeridas.
```

---

## Variables de entorno requeridas

La aplicacion no funcionara si alguna de estas variables no esta definida. En desarrollo local se leen del archivo `.env`. En produccion (Cloud Run), se configuran directamente en el servicio.

| Variable | Descripcion | Ejemplo |
|---|---|---|
| `WHATSAPP_PHONE_NUMBER_ID` | ID del numero de telefono de WhatsApp Business en Meta | `123456789012345` |
| `WHATSAPP_ACCESS_TOKEN` | Token de acceso permanente de Meta para autenticar las llamadas a la API | `EAABxxx...` |
| `WHATSAPP_VERIFY_TOKEN` | Token secreto inventado por el equipo para verificar el webhook al registrarlo en Meta | `mi_token_secreto_123` |
| `GCP_PROJECT_ID` | ID del proyecto en Google Cloud Platform | `mi-proyecto-gcp` |
| `BIGQUERY_DATASET` | Nombre del dataset en BigQuery donde se almacenan los mensajes | `whatsapp_messages` |
| `BIGQUERY_TABLE_SENT` | Nombre de la tabla donde se guardan los mensajes enviados | `sent_messages` |
| `BIGQUERY_TABLE_RECEIVED` | Nombre de la tabla donde se guardan los mensajes recibidos | `received_messages` |
| `API_AUTH_TOKEN` | Contrasena interna que el frontend debe enviar en cada peticion para autenticarse | `contrasena_segura_456` |

---

## Autenticacion de la API

Todos los endpoints (excepto el webhook de WhatsApp) estan protegidos. El cliente (frontend u otro sistema) debe incluir el `API_AUTH_TOKEN` en la cabecera de cada peticion de la siguiente forma:

```
Authorization: Bearer <valor_de_API_AUTH_TOKEN>
```

Si el token no es correcto o no se incluye, la API devuelve un error `401 Unauthorized`.

El webhook de WhatsApp (`/webhook`) no utiliza este sistema porque Meta no envia el token: en su lugar, se verifica con el `WHATSAPP_VERIFY_TOKEN` durante el proceso de registro.

---

## Endpoints de la API

La documentacion interactiva generada automaticamente por FastAPI esta disponible en `/docs` cuando la aplicacion esta corriendo.

A continuacion se describe cada endpoint:

---

### Estado del servicio

#### `GET /`

Devuelve un mensaje de confirmacion de que la API esta en funcionamiento. Util para saber si el servidor esta activo.

**Respuesta de ejemplo:**
```json
{"status": "ok", "service": "whatsapp-business-api"}
```

#### `GET /health`

Endpoint de verificacion de salud (health check). Cloud Run lo llama periodicamente para confirmar que el servicio esta disponible.

**Respuesta de ejemplo:**
```json
{"status": "healthy"}
```

---

### Mensajes (`/messages`)

Todos los endpoints de este grupo requieren autenticacion.

#### `POST /messages/send`

Envia un mensaje individual a un numero de telefono.

Soporta multiples tipos de contenido:
- **Texto**: Mensajes de texto plano.
- **Imagen**: Imagen con o sin pie de foto, referenciada por URL o por ID de media de Meta.
- **Video**: Video con o sin pie de foto.
- **Audio**: Archivo de audio.
- **Documento**: Archivo adjunto (PDF, DOCX, etc.).
- **Sticker**: Sticker de WhatsApp.
- **Interactivo (botones)**: Mensaje con hasta 3 botones de respuesta rapida.
- **Interactivo (lista)**: Mensaje con un menu de lista de opciones.
- **Template**: Mensaje usando una plantilla pre-aprobada por Meta (util para el primer contacto).

El mensaje enviado queda registrado automaticamente en BigQuery con su estado, fecha y numero de destino.

**Cuerpo de la peticion (ejemplo para texto):**
```json
{
  "to": "521234567890",
  "message_type": "text",
  "text": {"body": "Hola, este es un mensaje de prueba."}
}
```

**Respuesta de ejemplo:**
```json
{
  "message_id": "wamid.xxxxx",
  "status": "sent",
  "timestamp": "2024-01-15T10:30:00"
}
```

---

#### `POST /messages/send-bulk`

Envia el mismo mensaje a una lista de multiples numeros de telefono. Es el endpoint principal de las campanas masivas.

Recibe exactamente el mismo tipo de contenido que `/messages/send`, pero en lugar de un numero en `to`, recibe un arreglo `recipients` con todos los numeros de destino.

El sistema itera sobre cada destinatario de forma independiente: si un envio falla para un numero especifico, los demas continuan sin interrumpirse. Al final devuelve un resumen con cuantos fueron exitosos y cuantos fallaron.

**Cuerpo de la peticion (ejemplo):**
```json
{
  "recipients": ["521234567890", "521098765432", "521555000111"],
  "message_type": "text",
  "text": {"body": "Estimado cliente, le informamos que..."}
}
```

**Respuesta de ejemplo:**
```json
{
  "total": 3,
  "successful": 3,
  "failed": 0,
  "results": [...]
}
```

---

### Webhook (`/webhook`)

El webhook es el mecanismo por el cual Meta notifica al backend cuando un usuario envia un mensaje al numero de WhatsApp de la empresa.

#### `GET /webhook`

Este endpoint es exclusivamente para el proceso de verificacion inicial del webhook. Cuando se registra la URL del webhook en el panel de Meta for Developers, Meta hace una peticion GET a esta URL para confirmar que pertenece al dueno de la aplicacion. El backend responde con el `hub.challenge` que Meta envia, lo que confirma la autenticidad.

Este proceso solo ocurre una vez al momento de configurar o reconfigurar el webhook. No es llamado durante la operacion normal.

#### `POST /webhook`

Este es el endpoint que Meta llama cada vez que un usuario envia un mensaje al numero de WhatsApp de la empresa.

Al recibir la notificacion, el backend:
1. Extrae los datos del mensaje (numero de origen, texto o tipo de media, timestamp).
2. Determina el tipo de contenido: texto, imagen, video, audio, documento, sticker, ubicacion, contactos, o respuesta interactiva.
3. Guarda el registro completo del mensaje en la tabla `received_messages` de BigQuery, incluyendo el payload crudo de Meta para auditoria.
4. Responde a Meta con `{"status": "ok"}` para confirmar la recepcion. Si Meta no recibe esta confirmacion dentro de un tiempo limite, reintentara la notificacion.

---

### Historial (`/history`)

Requiere autenticacion.

#### `GET /history/campaigns`

Devuelve un resumen estadistico de las campanas de envio masivo realizadas, agrupadas por hora. Para cada bloque horario muestra el total de mensajes enviados, el numero de destinatarios unicos, y el timestamp del ultimo mensaje enviado en ese periodo.

Retorna las 20 campanas mas recientes en orden descendente (la mas reciente primero).

**Respuesta de ejemplo:**
```json
[
  {
    "campaign_hour": "2024-01-15T10:00:00",
    "total_messages": 450,
    "unique_recipients": 450,
    "last_sent": "2024-01-15T10:58:33"
  }
]
```

---

### Chat (`/chat`)

Requiere autenticacion.

#### `GET /chat/contacts`

Devuelve la lista de numeros de telefono de todos los usuarios que alguna vez han enviado un mensaje al numero de la empresa. Consulta directamente la tabla `received_messages` de BigQuery y retorna numeros unicos ordenados alfabeticamente.

**Respuesta de ejemplo:**
```json
["521234567890", "521098765432", "5215550001111"]
```

#### `GET /chat/messages/{phone_number}`

Devuelve el historial completo de conversacion con un numero de telefono especifico. Combina tanto los mensajes enviados a ese numero (desde `sent_messages`) como los mensajes recibidos de ese numero (desde `received_messages`), ordenados cronologicamente de mas antiguo a mas reciente.

Cada mensaje en el historial indica si fue de tipo `"sent"` (enviado por la empresa) o `"received"` (recibido del usuario).

Retorna un maximo de 100 mensajes.

**URL de ejemplo:** `GET /chat/messages/521234567890`

**Respuesta de ejemplo:**
```json
[
  {"message_id": "wamid.xxx", "content": "Hola, en que le podemos ayudar?", "timestamp": "2024-01-15T09:00:00", "type": "sent", "message_type": "text"},
  {"message_id": "wamid.yyy", "content": "Quisiera informacion sobre...", "timestamp": "2024-01-15T09:02:00", "type": "received", "message_type": "text"}
]
```

---

### Configuracion (`/settings`)

Requiere autenticacion.

#### `GET /settings/phone-numbers`

Devuelve la lista de numeros de telefono de WhatsApp Business que han sido registrados en el sistema. Util cuando la empresa opera con multiples numeros y el frontend necesita presentar opciones al usuario.

**Respuesta de ejemplo:**
```json
[
  {"alias": "Numero ventas", "phone_number_id": "123456789", "display_phone_number": "+52 55 1234 5678"},
  {"alias": "Numero soporte", "phone_number_id": "987654321", "display_phone_number": "+52 55 8765 4321"}
]
```

#### `POST /settings/phone-numbers`

Registra un nuevo numero de telefono de WhatsApp Business en el sistema. Requiere un alias descriptivo (nombre para identificarlo internamente), el Phone Number ID que proporciona Meta, y opcionalmente el numero en formato legible.

**Cuerpo de la peticion:**
```json
{
  "alias": "Numero ventas norte",
  "phone_number_id": "112233445566",
  "display_phone_number": "+52 81 1234 5678"
}
```

#### `POST /settings/media/upload`

Sube un archivo multimedia (imagen, video, audio, documento) a los servidores de Meta y devuelve el ID asignado por Meta. Este ID puede usarse posteriormente en los endpoints de envio de mensajes en lugar de una URL, lo que acelera el envio y reduce costos de ancho de banda cuando el mismo archivo se envia a muchos destinatarios.

El endpoint recibe el archivo como `multipart/form-data` y opcionalmente el `phone_number_id` que se usara para la subida si la cuenta tiene multiples numeros.

**Respuesta de ejemplo:**
```json
{"id": "1234567890123456"}
```

---

## Almacenamiento en BigQuery

El backend crea automaticamente el dataset y las tablas en BigQuery al iniciarse si no existen, por lo que no es necesario crearlos manualmente.

### Tabla: `sent_messages`

Registra cada mensaje enviado por el sistema.

| Campo | Tipo | Descripcion |
|---|---|---|
| `message_id` | STRING | ID unico asignado por Meta al mensaje |
| `to_number` | STRING | Numero de telefono del destinatario |
| `message_type` | STRING | Tipo de mensaje (text, image, document, etc.) |
| `content` | STRING | Contenido textual del mensaje |
| `status` | STRING | Estado del envio (sent, failed) |
| `sent_at` | TIMESTAMP | Fecha y hora del envio |
| `whatsapp_response` | STRING | Respuesta raw de la API de Meta (para auditoria) |

### Tabla: `received_messages`

Registra cada mensaje que un usuario envia al numero de la empresa.

| Campo | Tipo | Descripcion |
|---|---|---|
| `message_id` | STRING | ID unico asignado por Meta al mensaje |
| `from_number` | STRING | Numero de telefono del usuario que escribio |
| `message_type` | STRING | Tipo de mensaje recibido |
| `content` | STRING | Contenido textual o descriptor del tipo de media |
| `media_id` | STRING | ID del archivo multimedia (si aplica) |
| `received_at` | TIMESTAMP | Fecha y hora en que se recibio el mensaje |
| `raw_payload` | STRING | Payload JSON completo enviado por Meta (para auditoria) |

### Tabla: `phone_numbers`

Catalogo de los numeros de WhatsApp Business configurados en el sistema.

| Campo | Tipo | Descripcion |
|---|---|---|
| `alias` | STRING | Nombre descriptivo del numero |
| `phone_number_id` | STRING | ID del numero en la plataforma de Meta |
| `display_phone_number` | STRING | Numero en formato legible |

---

## Ejecucion en desarrollo local

```bash
# 1. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
cp .env.example .env
# Editar el archivo .env con los valores reales

# 4. Autenticarse con Google Cloud (para BigQuery)
gcloud auth application-default login

# 5. Iniciar el servidor
uvicorn main:app --reload --port 8000
```

La API queda disponible en: http://localhost:8000

Documentacion interactiva de endpoints: http://localhost:8000/docs

---

## Despliegue en produccion (Cloud Run)

Ver el archivo `DESPLIEGUE_GCP.md` para instrucciones detalladas sobre como desplegar el servicio en Google Cloud Run con integracion continua desde GitHub.
