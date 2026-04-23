import logging
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from models import SentMessageRecord, ReceivedMessageRecord
from config import get_settings

logger = logging.getLogger(__name__)



class BigQueryService:
    """Servicio para interactuar con BigQuery."""

    def __init__(self):
        """Inicializa el cliente de BigQuery y configura el dataset."""
        self.settings = get_settings()
        self.client = bigquery.Client(project=self.settings.gcp_project_id)
        self.dataset_id = f"{self.settings.gcp_project_id}.{self.settings.bigquery_dataset}"
        self._ensure_dataset_exists()
        self._ensure_tables_exist()

    def _ensure_dataset_exists(self) -> None:
        """Crea el dataset si no existe."""
        dataset = bigquery.Dataset(self.dataset_id)
        dataset.location = "US"
        try:
            self.client.get_dataset(self.dataset_id)
        except NotFound:
            self.client.create_dataset(dataset, exists_ok=True)

    def _ensure_tables_exist(self) -> None:
        """Crea las tablas necesarias si no existen."""
        sent_schema = [
            bigquery.SchemaField("message_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("to_number", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("message_type", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("content", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("sent_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("whatsapp_response", "STRING", mode="NULLABLE"),
        ]

        received_schema = [
            bigquery.SchemaField("message_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("from_number", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("message_type", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("content", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("media_id", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("received_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("raw_payload", "STRING", mode="REQUIRED"),
        ]

        self._create_table_if_not_exists(self.settings.bigquery_table_sent, sent_schema)
        self._create_table_if_not_exists(self.settings.bigquery_table_received, received_schema)

        # Migración: Verificar si la columna is_read existe
        received_table_id = f"{self.dataset_id}.{self.settings.bigquery_table_received}"
        try:
            table = self.client.get_table(received_table_id)
            if not any(f.name == "is_read" for f in table.schema):
                new_schema = table.schema[:]
                new_schema.append(bigquery.SchemaField("is_read", "BOOLEAN", mode="NULLABLE"))
                table.schema = new_schema
                self.client.update_table(table, ["schema"])
        except Exception as e:
            logger.error(f"Error checking/updating received_messages schema: {e}")

        phone_numbers_schema = [
            bigquery.SchemaField("alias", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("phone_number_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("display_phone_number", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("waba_id", "STRING", mode="NULLABLE"),
        ]
        self._create_table_if_not_exists("phone_numbers", phone_numbers_schema)
        
        # Migración: Verificar si la columna waba_id existe
        table_id = f"{self.dataset_id}.phone_numbers"
        try:
            table = self.client.get_table(table_id)
            if not any(f.name == "waba_id" for f in table.schema):
                new_schema = table.schema[:]
                new_schema.append(bigquery.SchemaField("waba_id", "STRING", mode="NULLABLE"))
                table.schema = new_schema
                self.client.update_table(table, ["schema"])
        except Exception as e:
            logger.error(f"Error checking/updating phone_numbers schema: {e}")

        users_schema = [
            bigquery.SchemaField("user_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("username", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("password_hash", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("role", "STRING", mode="NULLABLE"),
        ]
        self._create_table_if_not_exists("users", users_schema)

        # Migración: Verificar si la columna role existe
        users_table_id = f"{self.dataset_id}.users"
        try:
            table = self.client.get_table(users_table_id)
            if not any(f.name == "role" for f in table.schema):
                new_schema = table.schema[:]
                new_schema.append(bigquery.SchemaField("role", "STRING", mode="NULLABLE"))
                table.schema = new_schema
                self.client.update_table(table, ["schema"])
        except Exception as e:
            logger.error(f"Error checking/updating users schema: {e}")

    def _create_table_if_not_exists(self, table_name: str, schema: list) -> None:
        """Crea una tabla con el esquema especificado si no existe."""
        table_id = f"{self.dataset_id}.{table_name}"
        table = bigquery.Table(table_id, schema=schema)
        try:
            self.client.get_table(table_id)
        except NotFound:
            self.client.create_table(table)

    def get_phone_numbers(self) -> list[dict]:
        """Obtiene la lista de numeros de telefono configurados."""
        query = f"""
            SELECT alias, phone_number_id, display_phone_number, waba_id
            FROM `{self.dataset_id}.phone_numbers`
        """
        query_job = self.client.query(query)
        results = query_job.result()
        return [dict(row) for row in results]

    def add_phone_number(self, alias: str, phone_number_id: str, display_phone_number: str = None, waba_id: str = None) -> None:
        """Agrega un nuevo numero de telefono a la configuracion."""
        table_id = f"{self.dataset_id}.phone_numbers"
        rows_to_insert = [
            {
                "alias": alias,
                "phone_number_id": phone_number_id,
                "display_phone_number": display_phone_number,
                "waba_id": waba_id,
            }
        ]
        errors = self.client.insert_rows_json(table_id, rows_to_insert)
        if errors:
            raise Exception(f"Error inserting phone number: {errors}")

    def insert_sent_message(self, record: SentMessageRecord) -> None:
        """Inserta un registro de mensaje enviado en BigQuery."""
        table_id = f"{self.dataset_id}.{self.settings.bigquery_table_sent}"
        rows_to_insert = [
            {
                "message_id": record.message_id,
                "to_number": record.to_number,
                "message_type": record.message_type,
                "content": record.content,
                "status": record.status,
                "sent_at": record.sent_at.isoformat(),
                "whatsapp_response": record.whatsapp_response,
            }
        ]
        errors = self.client.insert_rows_json(table_id, rows_to_insert)
        if errors:
            logger.error(f"Error al insertar mensaje enviado en BigQuery: {errors}")
            raise Exception(f"Error inserting sent message: {errors}")
        logger.info(f"Mensaje enviado insertado en BigQuery: {record.message_id}")

    def insert_received_message(self, record: ReceivedMessageRecord) -> None:
        """Inserta un registro de mensaje recibido en BigQuery."""
        table_id = f"{self.dataset_id}.{self.settings.bigquery_table_received}"
        rows_to_insert = [
            {
                "message_id": record.message_id,
                "from_number": record.from_number,
                "message_type": record.message_type,
                "content": record.content,
                "media_id": record.media_id,
                "received_at": record.received_at.isoformat(),
                "raw_payload": record.raw_payload,
                "is_read": False,
            }
        ]
        errors = self.client.insert_rows_json(table_id, rows_to_insert)
        if errors:
            logger.error(f"Error al insertar mensaje recibido en BigQuery: {errors}")
            raise Exception(f"Error inserting received message: {errors}")
        logger.info(f"Mensaje recibido insertado en BigQuery: {record.message_id}")

    def update_message_status(self, message_id: str, new_status: str, error_details: str = None) -> None:
        """Actualiza el estado de un mensaje enviado utilizando DML UPDATE."""
        table_id = f"{self.dataset_id}.{self.settings.bigquery_table_sent}"
        
        query = f"""
            UPDATE `{table_id}`
            SET status = @new_status
        """
        
        query_parameters = [
            bigquery.ScalarQueryParameter("new_status", "STRING", new_status),
            bigquery.ScalarQueryParameter("message_id", "STRING", message_id)
        ]

        if error_details:
            query += ", whatsapp_response = @error_details"
            query_parameters.append(bigquery.ScalarQueryParameter("error_details", "STRING", error_details))

        query += " WHERE message_id = @message_id"

        job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
        
        try:
            query_job = self.client.query(query, job_config=job_config)
            query_job.result()  # Esperar a que termine la transaccion
            logger.info(f"Estado del mensaje {message_id} actualizado a {new_status} en BigQuery")
        except Exception as e:
            logger.error(f"Error actualizando estado en BigQuery para {message_id}: {str(e)}")

    def get_contacts(self) -> list[dict]:
        """Obtiene una lista de numeros de telefono (contactos), preview del ultimo mensaje y conteo de no leídos."""
        query = f"""
            WITH all_messages AS (
                SELECT 
                    from_number as phone, 
                    content,
                    received_at as timestamp,
                    IF(is_read = FALSE, 1, 0) as unread,
                    received_at as latest_received
                FROM `{self.dataset_id}.{self.settings.bigquery_table_received}`
                
                UNION ALL
                
                SELECT 
                    to_number as phone, 
                    content,
                    sent_at as timestamp,
                    0 as unread,
                    NULL as latest_received
                FROM `{self.dataset_id}.{self.settings.bigquery_table_sent}`
            ),
            ranked_messages AS (
                SELECT 
                    phone,
                    content as last_message,
                    timestamp as last_timestamp,
                    unread,
                    latest_received,
                    ROW_NUMBER() OVER(PARTITION BY RIGHT(phone, 10) ORDER BY timestamp DESC) as rn
                FROM all_messages
                WHERE phone IS NOT NULL AND LENGTH(phone) >= 10
            )
            SELECT 
                MAX(phone) as phone,
                MAX(CASE WHEN rn = 1 THEN last_message END) as last_message,
                MAX(CASE WHEN rn = 1 THEN last_timestamp END) as last_timestamp,
                SUM(unread) as unread_count,
                MAX(latest_received) as last_received_time
            FROM ranked_messages
            GROUP BY RIGHT(phone, 10)
            ORDER BY last_timestamp DESC
        """
        query_job = self.client.query(query)
        results = query_job.result()
        
        contacts = []
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        for row in results:
            window_open = False
            remaining_hours = 0
            if row.last_received_time:
                diff_seconds = (now - row.last_received_time).total_seconds()
                if diff_seconds < 24 * 3600:
                    window_open = True
                    remaining_hours = max(0, 24 - (diff_seconds / 3600))
            
            contacts.append({
                "phone": row.phone, 
                "unread_count": row.unread_count,
                "last_message": row.last_message,
                "last_timestamp": row.last_timestamp.isoformat() if row.last_timestamp else None,
                "window_open": window_open,
                "remaining_hours": round(remaining_hours, 2)
            })
        return contacts

    def get_chat_history(self, phone_number: str) -> list[dict]:
        """Obtiene el historial de chat (enviados y recibidos) para un numero."""
        query = f"""
            SELECT * FROM (
                SELECT message_id, content, sent_at as timestamp, 'sent' as type, message_type, NULL as media_id, status
                FROM `{self.dataset_id}.{self.settings.bigquery_table_sent}`
                WHERE RIGHT(to_number, 10) = RIGHT(@phone_number, 10)
                AND status != 'failed'
                UNION ALL
                SELECT message_id, content, received_at as timestamp, 'received' as type, message_type, media_id, NULL as status
                FROM `{self.dataset_id}.{self.settings.bigquery_table_received}`
                WHERE RIGHT(from_number, 10) = RIGHT(@phone_number, 10)
            )
            ORDER BY timestamp DESC
            LIMIT 100
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("phone_number", "STRING", phone_number)
            ]
        )
        query_job = self.client.query(query, job_config=job_config)
        results = query_job.result()
        messages = [dict(row) for row in results]
        return list(reversed(messages))

    def mark_chat_read(self, phone_number: str) -> None:
        """Marca todos los mensajes recibidos de un numero como leídos."""
        table_id = f"{self.dataset_id}.{self.settings.bigquery_table_received}"
        query = f"""
            UPDATE `{table_id}`
            SET is_read = TRUE
            WHERE RIGHT(from_number, 10) = RIGHT(@phone_number, 10)
            AND (is_read = FALSE OR is_read IS NULL)
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("phone_number", "STRING", phone_number)
            ]
        )
        try:
            query_job = self.client.query(query, job_config=job_config)
            query_job.result()
        except Exception as e:
            logger.error(f"Error marking chat {phone_number} as read: {e}")

    def get_campaign_stats(self) -> list[dict]:
        """Obtiene estadisticas de campañas recientes (agrupadas por hora)."""
        query = f"""
            SELECT 
                TIMESTAMP_TRUNC(sent_at, HOUR) as campaign_hour,
                COUNT(*) as total_messages,
                COUNT(DISTINCT to_number) as unique_recipients,
                MAX(sent_at) as last_sent
            FROM `{self.dataset_id}.{self.settings.bigquery_table_sent}`
            GROUP BY 1
            ORDER BY 1 DESC
            LIMIT 20
        """
        query_job = self.client.query(query)
        results = query_job.result()
        return [dict(row) for row in results]

    def add_user(self, user_id: str, username: str, password_hash: str, role: str = "agent") -> None:
        """Agrega un nuevo usuario a BigQuery."""
        table_id = f"{self.dataset_id}.users"
        rows_to_insert = [
            {
                "user_id": user_id,
                "username": username,
                "password_hash": password_hash,
                "role": role,
            }
        ]
        errors = self.client.insert_rows_json(table_id, rows_to_insert)
        if errors:
            raise Exception(f"Error inserting user: {errors}")


_bigquery_service: BigQueryService | None = None


def get_bigquery_service() -> BigQueryService:
    """Obtiene la instancia singleton del servicio de BigQuery."""
    global _bigquery_service
    if _bigquery_service is None:
        _bigquery_service = BigQueryService()
    return _bigquery_service



