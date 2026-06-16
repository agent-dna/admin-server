import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

class Settings:
    admin_server_port: int = int(os.getenv("ADMIN_SERVER_PORT", "8000"))
    agentdna_api_key: str = os.getenv("AGENTDNA_API_KEY", "")
    agentdna_chain_url: str = os.getenv("AGENTDNA_CHAIN_URL", "")
    database_url: str = os.getenv("DATABASE_URL", "")
    jwt_secret: str = os.getenv("JWT_SECRET", "")
    jwt_expiry_minutes: int = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))

settings = Settings()
