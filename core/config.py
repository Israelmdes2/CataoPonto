from functools import lru_cache
from pathlib import Path
from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Aplicação
    PROJECT_NAME: str = "EnvioCartaoPonto"
    PROJECT_VERSION: str = "1.0.0"
    ENV: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Segurança
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080

    # Logging & Banco
    LOG_LEVEL: str = "INFO"
    DATABASE_URL: str = "sqlite+aiosqlite:///./infrastructure/database/app.db"
    CORS_ORIGINS: list[str] = ["*"]

    # ==========================================
    # Configurações do Processo - RH Cartão Ponto
    # ==========================================

    # Pastas e Diretórios de Rede
    REDE_PASTA_CONSOLIDADO: str = r"C:\Digitaly\EnvioCartaoPonto\data\consolidado"
    REDE_PASTA_INDIVIDUAIS: str = r"C:\Digitaly\EnvioCartaoPonto\data\individuais"
    REDE_PASTA_RELATORIOS: str = r"C:\Digitaly\EnvioCartaoPonto\data\relatorios"
    PLANILHA_COLABORADORES_PATH: str = r"C:\Digitaly\EnvioCartaoPonto\data\colaboradores.xlsx"

    # Senior Desktop (Automação por Imagem)
    SENIOR_EXECUTAVEL_HML: Optional[str] = None
    SENIOR_EXECUTAVEL_PROD: Optional[str] = None
    SENIOR_EXECUTAVEL: Optional[str] = None  # Retrocompatibilidade
    SENIOR_PASTA_ATALHO: str = "Senior"
    SENIOR_NOME_MODULO: str = "Controle de Ponto e Refeitório"
    SENIOR_LOGIN: str = ""
    SENIOR_PASSWORD: str = ""
    SENIOR_TEMPLATES_DIR: str = str(BASE_DIR / "assets" / "templates")
    SENIOR_CONFIDENCE: float = 0.85
    SENIOR_TIMEOUT_RELATORIO_SEGUNDOS: int = 1200  # 20 min

    # E-mail (SMTP Office365 / Unimed)
    SMTP_HOST: str = "smtp.office365.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = "digitaly.tech@unimedvaledoaco.coop.br"
    SMTP_PASSWORD: str = ""
    EMAIL_REMETENTE: str = "digitaly.tech@unimedvaledoaco.coop.br"
    EMAIL_TESTE_MODO: bool = False
    EMAIL_TESTE_DESTINO: Optional[str] = None

    @field_validator("SENIOR_LOGIN", mode="after")
    @classmethod
    def normalizar_senior_login(cls, v: str) -> str:
        return v.strip().lower() if v else ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
