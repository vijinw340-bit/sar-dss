"""Application configuration loaded from environment / .env file."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings object. Values are overridable via environment variables."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # App
    APP_NAME: str = "SAR-DSS"
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True

    # Security
    SECRET_KEY: str = "change-me-to-a-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Database
    DATABASE_URL: str = "sqlite:///./sar_dss.db"
    POSTGRES_USER: str = "sar"
    POSTGRES_PASSWORD: str = "dss_password"
    POSTGRES_DB: str = "sar_dss"

    # CORS - comma separated list of allowed origins
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Bootstrap admin
    ADMIN_USERNAME: str = "admin"
    ADMIN_EMAIL: str = "admin@sar-dss.aai.gov.in"
    ADMIN_PASSWORD: str = "Admin@123"

    # Weather
    WEATHER_PROVIDER: str = "openmeteo"
    WEATHER_API_KEY: str = ""

    # Reports
    MAP_TILE_PROVIDER: str = "carto"
    REPORT_DIR: str = "./reports"

    # Outbound egress (VPN / proxy routing for weather, static maps & tiles).
    # Modes: direct | rotate | random | failover | chain | relay | guard | mixnet
    #   (see app/services/netroute.py). ssh:// proxies spawn a local SSH jump).
    OUTBOUND_MODE: str = "direct"
    # Comma separated proxy URLs for rotate / random / failover / guard modes.
    # Supports socks5://, socks4://, http://, https:// (e.g. a local VPN SOCKS
    # endpoint) and ssh://user@host[:port] for an SSH dynamic-tunnel jump.
    OUTBOUND_PROXIES: str = ""
    # Two or more proxies joined by "->" for chain mode (multi-hop egress).
    OUTBOUND_PROXY_CHAIN: str = ""
    # Base URL of a URL-forwarding relay (e.g. r.jina.ai) for relay mode. Path format.
    OUTBOUND_RELAY_URL: str = ""
    # Base URL of an image relay (e.g. https://wsrv.nl) for tiles & static maps.
    # Requires "?url=" query parameter (wsrv/weserv style) - query format.
    OUTBOUND_IMAGE_RELAY_URL: str = ""
    # Relay URL format for image relays: query | duckduckgo (see netroute.py).
    OUTBOUND_IMAGE_RELAY_FORMAT: str = "query"
    OUTBOUND_CONNECT_TIMEOUT: float = 15.0

    @property
    def cors_origin_list(self) -> list[str]:
        """Split the comma separated CORS_ORIGINS string into a list."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
