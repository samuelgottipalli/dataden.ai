from ldap3 import Server, Connection
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=r"G:\dataden.ai\autogen-mcp-system\config\.env")

try:
    server = Server(
        os.getenv("LDAP_SERVER"),
        port=int(os.getenv("LDAP_PORT")),
        use_ssl=(os.getenv("LDAP_USE_SSL") == "true"),
    )
    conn = Connection(
        server,
        user=os.getenv("LDAP_SERVICE_ACCOUNT_USER"),
        password=os.getenv("LDAP_SERVICE_ACCOUNT_PASSWORD"),
        auto_bind=True,
    )
    print("✓ LDAP Connection Successful!")
    conn.unbind()
except Exception as e:
    print(f"✗ LDAP Connection Failed: {e}")
