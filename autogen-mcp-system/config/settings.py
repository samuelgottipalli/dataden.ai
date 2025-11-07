from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings from environment variables"""

    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gpt-oss:120b-cloud"
    ollama_model_info: dict[str, str | bool] = {
        "vision": True,
        "function_calling": True,
        "json_output": True,
        "family": "gpt-oss",
        "structured_output": True,
    }

    # MS SQL Server
    mssql_server: str
    mssql_port: int = 1433
    mssql_database: str
    mssql_user: str
    mssql_password: str
    mssql_driver: str = "{ODBC Driver 18 for SQL Server}"

    # LDAP
    ldap_server: str
    ldap_port: int = 389
    ldap_domain: str
    ldap_base_dn: str
    ldap_user_dn_pattern: str
    ldap_service_account_user: str
    ldap_service_account_password: str
    ldap_use_ssl: bool = False

    # MCP Server
    mcp_server_host: str = "127.0.0.1"
    mcp_server_port: int = 8000
    mcp_api_prefix: str = "/mcp"

    # Agents
    agent_retry_attempts: int = 3
    agent_escalation_email: str
    log_level: str = "INFO"

    # Security
    secret_key: str
    jwt_expiration_hours: int = 24

    # OpenWebUI Integration
    openwebui_api_key: str = ""

    class Config:
        env_file = r"G:\dataden.ai\autogen-mcp-system\config\.env"
        case_sensitive = False


settings = Settings()
