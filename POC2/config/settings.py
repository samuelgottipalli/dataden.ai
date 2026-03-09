"""
config/settings.py
AI Data Assistant — POC2

Central configuration. All values are loaded from the .env file.
Import the singleton `settings` object wherever config is needed:

    from config.settings import settings

Multi-database support: individual database names are NOT stored here.
They live in config/databases.json and are loaded by db/catalog.py.
The mssql_* fields here define the server-level connection credentials
that are shared across all databases on that server.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables / .env file.
    All fields with no default are required — the app will not start if they
    are missing.
    """

    # --- MS SQL Server (server-level — no single database field) ---
    mssql_server: str
    mssql_port: int = 1433
    mssql_user: str
    mssql_password: str
    mssql_driver: str = "{ODBC Driver 18 for SQL Server}"
    mssql_trust_server_certificate: str = "yes"

    # --- PostgreSQL ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "ai_assistant_db"
    postgres_user: str = "postgres"
    postgres_password: str

    # --- LDAP ---
    ldap_server: str
    ldap_port: int = 389
    ldap_base_dn: str
    ldap_domain: str
    ldap_user_dn_pattern: str
    ldap_service_account_user: str
    ldap_service_account_password: str
    ldap_use_ssl: bool = False

    # --- Ollama ---
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:latest"
    ollama_embed_model: str = "nomic-embed-text"

    # --- FastAPI ---
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # --- Application ---
    log_level: str = "INFO"
    admin_email: str
    secret_key: str

    # --- Derived convenience properties ---

    def mssql_connection_string(self, database: str) -> str:
        """
        Returns the pyodbc connection string for a specific database on the
        configured MS SQL Server. Pass the database name from databases.json.

        Example:
            conn_str = settings.mssql_connection_string("StudentDB")
        """
        return (
            f"DRIVER={self.mssql_driver};"
            f"SERVER={self.mssql_server},{self.mssql_port};"
            f"DATABASE={database};"
            f"UID={self.mssql_user};"
            f"PWD={self.mssql_password};"
            f"TrustServerCertificate={self.mssql_trust_server_certificate};"
        )

    @property
    def postgres_connection_string(self) -> str:
        """Returns the psycopg2 DSN for the operational PostgreSQL database."""
        return (
            f"host={self.postgres_host} "
            f"port={self.postgres_port} "
            f"dbname={self.postgres_db} "
            f"user={self.postgres_user} "
            f"password={self.postgres_password}"
        )

    @property
    def postgres_url(self) -> str:
        """Returns the SQLAlchemy-compatible PostgreSQL URL."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Singleton — import this everywhere
settings = Settings()
