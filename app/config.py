"""
WinoWin Recepcionista — Configuración centralizada
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env file
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

# ── Paths ──────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


@dataclass
class Config:
    """Configuración desde variables de entorno."""

    # Meta / WhatsApp
    whatsapp_token: str = field(
        default_factory=lambda: os.getenv("WHATSAPP_TOKEN", "")
    )
    phone_number_id: str = field(
        default_factory=lambda: os.getenv("PHONE_NUMBER_ID", "1103593682842997")
    )
    waba_id: str = field(
        default_factory=lambda: os.getenv("WABA_ID", "975958184791108")
    )

    # Webhook verification
    verify_token: str = "winowin_recepcionista_2026"

    # Meta API
    graph_api_version: str = "v22.0"
    graph_api_base: str = "https://graph.facebook.com"

    # Groq AI
    groq_api_key: str = field(
        default_factory=lambda: os.getenv("GROQ_API_KEY", "")
    )
    groq_model: str = "llama-3.3-70b-versatile"
    groq_max_tokens: int = 512
    groq_temperature: float = 0.7

    # Database
    database_path: str = field(
        default_factory=lambda: str(DATA_DIR / "chatbot.db")
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Business
    business_name: str = field(
        default_factory=lambda: os.getenv("BUSINESS_NAME", "Peluquería WinoWin")
    )
    business_type: str = field(
        default_factory=lambda: os.getenv("BUSINESS_TYPE", "peluquería")
    )

    @property
    def groq_enabled(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def can_send_messages(self) -> bool:
        """Indica si el token permite enviar mensajes (no bloqueado por Meta)."""
        return bool(self.whatsapp_token)

    @property
    def messages_api_url(self) -> str:
        return f"{self.graph_api_base}/{self.graph_api_version}/{self.phone_number_id}/messages"

    @property
    def health_api_url(self) -> str:
        return f"{self.graph_api_base}/{self.graph_api_version}/{self.phone_number_id}/health_assurance"


# Singleton
config = Config()
