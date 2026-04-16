from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Configuracion de la aplicacion."""

    whatsapp_api_url: str = "https://graph.facebook.com/v22.0"
    whatsapp_phone_number_id: str
    whatsapp_access_token: str
    whatsapp_verify_token: str
    whatsapp_business_account_id: str | None = None
    gcp_project_id: str
    bigquery_dataset: str = "whatsapp_messages"
    bigquery_table_sent: str = "sent_messages"
    bigquery_table_received: str = "received_messages"
    api_auth_token: str

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    """Obtiene la configuracion cacheada de la aplicacion."""
    return Settings()



