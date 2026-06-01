import ssl
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import truststore
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from pydantic_ai.models.groq import GroqModel


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "llama-3.3-70b-versatile"

    data_dir: Path = Path("./data")
    host: str = "127.0.0.1"
    port: int = 8000

    @field_validator("groq_api_key", mode="before")
    @classmethod
    def require_groq_key(cls, v: str) -> str:
        if not v:
            raise ValueError(
                "GROQ_API_KEY is not set — add it to your .env file"
            )
        return v

    @property
    def cover_letters_dir(self) -> Path:
        return self.data_dir / "cover_letters"


settings = Settings()

_ssl_ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(verify=_ssl_ctx)
    return _http_client


def make_groq_model() -> "GroqModel":
    from pydantic_ai.models.groq import GroqModel
    from pydantic_ai.providers.groq import GroqProvider

    provider = GroqProvider(
        api_key=settings.groq_api_key.get_secret_value(),
        http_client=_get_http_client(),
    )
    return GroqModel(settings.groq_model, provider=provider)
