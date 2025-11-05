import pyodbc
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=r"G:\dataden.ai\autogen-mcp-system\config\.env")

try:
    conn_str = (
        f"DRIVER={os.getenv('MSSQL_DRIVER')};"
        f"SERVER={os.getenv('MSSQL_SERVER')};"
        f"DATABASE={os.getenv('MSSQL_DATABASE')};"
        f"UID={os.getenv('MSSQL_USER')};"
        f"PWD={os.getenv('MSSQL_PASSWORD')};"
        f"TrustServerCertificate=yes;"
    )
    conn = pyodbc.connect(conn_str)
    print("✓ MS SQL Connection Successful!")
    cursor = conn.cursor()
    cursor.execute("SELECT TOP 1 * FROM INFORMATION_SCHEMA.TABLES")
    print("✓ Query executed. Sample table found.")
    conn.close()
except Exception as e:
    print(f"✗ Connection Failed: {e}")
