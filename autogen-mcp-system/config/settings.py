from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings from environment variables"""

    # Ollama - PRIMARY MODEL
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gpt-oss:120b-cloud"
    ollama_model_info: dict[str, str | bool] = {
        "vision": True,
        "function_calling": True,
        "json_output": True,
        "family": "gpt-oss",
        "structured_output": True,
    }

    # Fallback Model Configuration
    ollama_fallback_model: str = "llama3.2:3b"
    enable_fallback: bool = True
    fallback_after_attempts: int = 2

    # Token and Context Configuration
    max_tokens: int = 8000  # INCREASED from 4000
    temperature: float = 0.3

    # Rate Limiting
    max_retries_per_query: int = 3
    retry_delay_seconds: int = 2

    # API Quota Limits
    api_quota_daily_limit: int = 1000
    api_quota_warn_percentage: float = 0.8
    api_quota_reset_hour: int = 0

    # Usage Tracking
    track_token_usage: bool = True
    usage_log_file: str = "logs/api_usage.log"

    # User Notifications
    notify_on_fallback: bool = True
    notify_on_quota_warning: bool = True
    show_token_count: bool = False
    
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
